"""Entrenamiento y validación del modelo CacaoResiliente (Fase 4).

    ml/.venv/bin/python -m ml.train                 # compara modelos, valida y guarda artefactos
    ml/.venv/bin/python -m ml.train --perm 300      # + test de permutación (¿hay señal real?)

Qué hace:
  1. Compara, con leave-one-year-out (LOYO) sin fuga, líneas base vs Ridge vs GBR cuantílico
     vs ensamble. El peso del ensamble se elige de forma anidada.
  2. Calibra el intervalo p10–p90 por nivel (conformal: cuantiles de los residuos LOYO).
  3. Robustez: bloques de 3 años, otros umbrales, sin restricción de signo, sin pesos, solo
     serie nacional, target de rendimiento, sin 1983/1998, desde 1999, y corrección de sesgo
     climática reajustada sin el año de test (1983, 1998).
  4. Ajusta el modelo final con todos los datos y guarda:
        artifacts/cacao_loss_v1.joblib      bundle para el backend (dict; ver ml/inference.py)
        artifacts/model_card_v1.json        fórmula, coeficientes, métricas y límites
        artifacts/cv_predictions_v1.csv     predicción fuera de muestra de cada área-año
"""
from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from datetime import date
from functools import partial

import joblib
import numpy as np
import pandas as pd

from .config import ARTIFACTS, DATA_PROCESSED
from .dataset import OUTPUT, OUTPUT_BY_LEVEL, TARGET, TREND_SPAN_YEARS
from .model import (CORE, EXCLUDE_AREAS, FACTOR_GROUPS, CacaoLossModel, FeatureSpec,
                    QuantileGBR, RidgeModel, hinge_name)
from .inference import build_bundle
from .scenarios import load_climate, scenario_features, scenario_years
from .validation import NinoBaseline, fold_targets, loyo

VERSION = "v1"
W_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
BIG_LOSS = 20.0            # % de pérdida a partir del cual un año es "malo"
KEY = ["area_name", "year"]
EVENT_YEARS = [1983, 1987, 1992, 1998, 2012, 2016, 2017, 2023, 2024]
EXTREME_YEARS = [1983, 1998]
# La tendencia LOWESS de un año solo usa los ±TREND_SPAN/2 años vecinos: al calibrar algo con
# las predicciones de "los demás años" se quitan también esos vecinos, porque su target sí
# depende del resultado del año de test.
CALIB_GAP = TREND_SPAN_YEARS // 2 + 1


# ── Datos ─────────────────────────────────────────────────────────────────────────────
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Panel de entrenamiento (sin las áreas excluidas) y tabla climática completa área × año."""
    panel = pd.read_parquet(DATA_PROCESSED / "training_panel.parquet")
    panel = panel[~panel.area_name.isin(EXCLUDE_AREAS)].reset_index(drop=True)
    climate = pd.read_parquet(DATA_PROCESSED / "features_area_year.parquet")
    return panel, climate


# ── Líneas base ───────────────────────────────────────────────────────────────────────
class Zero:
    """Sin información climática: predice 'año normal' (anomalía 0)."""

    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.zeros(len(X))


class OniBaseline:
    """Media histórica de los años Niño vs no-Niño según el ONI (lo que haría un análisis simple)."""

    def fit(self, X, y):
        n = X.is_nino == 1
        self.nino, self.rest = y[n].mean(), y[~n].mean()
        return self

    def predict(self, X):
        return np.where(X.is_nino == 1, self.nino, self.rest)


class ExtremeStep:
    """Escalón de 2 parámetros: lluvia > +100 % → media de los otros años extremos; si no, media.
    Es la regla más simple que captura 1983/1998; el modelo debe estar a su altura."""

    def __init__(self, col: str = "rain_anom_pct", threshold: float = 100.0):
        self.col, self.threshold = col, threshold

    def fit(self, X, y):
        ext = X[self.col] > self.threshold
        self.ext = y[ext].mean() if ext.any() else y.mean()
        self.rest = y[~ext].mean()
        return self

    def predict(self, X):
        return np.where(X[self.col] > self.threshold, self.ext, self.rest)


# ── Métricas ──────────────────────────────────────────────────────────────────────────
def score(cv: pd.DataFrame) -> dict:
    e = cv.y_cv - cv.pred
    m = {"n": int(len(cv)), "mae": float(e.abs().mean()), "rmse": float(np.sqrt((e ** 2).mean())),
         "corr": float(cv.y_cv.corr(cv.pred)) if cv.pred.std() > 0 else None,
         # R² fuera de muestra respecto a "año normal": 1 − Σ(y−ŷ)² / Σy²
         "r2_oos": float(1 - (e ** 2).sum() / (cv.y_cv ** 2).sum())}
    if {"p10", "p90"} <= set(cv.columns):
        m["coverage_80"] = float(((cv.y_cv >= cv.p10) & (cv.y_cv <= cv.p90)).mean())
        m["interval_width"] = float((cv.p90 - cv.p10).mean())
    big = cv.y_cv < -BIG_LOSS
    if big.any():
        m["big_loss_n"] = int(big.sum())
        m["big_loss_hit"] = float((cv.pred[big] < -BIG_LOSS / 2).mean())       # avisó (≥ mitad)
        m["false_alarm"] = float((cv.pred[~big] < -BIG_LOSS).mean())
    return m


def by_level(cv: pd.DataFrame) -> dict:
    return {"national": score(cv[cv.level == "national"]), "province": score(cv[cv.level == "province"])}


def skill(cv: pd.DataFrame, base: pd.DataFrame, level: str) -> dict:
    """1 − error/error_base (MAE y RMSE) en un nivel."""
    a = cv[cv.level == level].set_index(KEY)
    b = base.set_index(KEY).reindex(a.index)
    ea, eb = a.y_cv - a.pred, b.y_cv - b.pred
    return {"mae": float(1 - ea.abs().mean() / eb.abs().mean()),
            "rmse": float(1 - np.sqrt((ea ** 2).mean()) / np.sqrt((eb ** 2).mean()))}


# ── Ensamble anidado e intervalos conformales ─────────────────────────────────────────
def _area_scale(cv: pd.DataFrame) -> pd.Series:
    return cv.groupby("area_name").y_cv.std()


def best_weight(df: pd.DataFrame) -> float:
    """w que minimiza el error cuadrático ponderado (1/s_a²) de w·ridge + (1−w)·gbr."""
    wt = 1 / df.area_name.map(_area_scale(df)) ** 2
    loss = {w: float((wt * (df.y_cv - (w * df.ridge + (1 - w) * df.gbr)) ** 2).sum()) for w in W_GRID}
    return min(loss, key=loss.get)


def _calib(cv: pd.DataFrame, yr: int) -> pd.DataFrame:
    """Filas para calibrar el año `yr`: sin ese año ni sus vecinos de tendencia."""
    return cv[(cv.year - yr).abs() >= CALIB_GAP]


def nested_ensemble(cv_ridge: pd.DataFrame, cv_gbr: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Para cada año de test, w se elige SOLO con las predicciones LOYO de años lejanos
    (fuera de la ventana de tendencia del año de test)."""
    df = cv_ridge.rename(columns={"pred": "ridge"}).merge(
        cv_gbr[KEY + ["pred"]].rename(columns={"pred": "gbr"}), on=KEY)
    w_year = pd.Series({yr: best_weight(_calib(df, yr)) for yr in sorted(df.year.unique())})
    w = df.year.map(w_year)
    df["pred"] = w * df.ridge + (1 - w) * df.gbr
    return df.drop(columns=["ridge", "gbr"]), w_year


def conformal_q(cv: pd.DataFrame, scale: pd.Series) -> tuple[float, float]:
    """Cuantiles 0.1 / 0.9 (hacia fuera) de los residuos normalizados r/s_a."""
    r = ((cv.y_cv - cv.pred) / cv.area_name.map(scale)).to_numpy()
    return float(np.quantile(r, 0.1, method="lower")), float(np.quantile(r, 0.9, method="higher"))


def level_q(cv: pd.DataFrame, scale: pd.Series) -> dict:
    """Cuantiles conformales por nivel (la serie nacional y las provincias tienen ruidos distintos)."""
    return {lvl: conformal_q(cv[cv.level == lvl], scale) for lvl in ("national", "province")
            if (cv.level == lvl).any()}


def add_conformal(cv: pd.DataFrame) -> pd.DataFrame:
    """p10/p90 de cada año de test con los residuos y escalas de años lejanos (ver `_calib`)."""
    out = []
    for yr, test in cv.groupby("year"):
        rest = _calib(cv, yr)
        scale = _area_scale(rest)
        q = level_q(rest, scale)
        s = test.area_name.map(scale)
        lo = test.level.map(lambda l: q.get(l, q.get("national"))[0])
        hi = test.level.map(lambda l: q.get(l, q.get("national"))[1])
        out.append(test.assign(p10=test.pred + s * lo, p90=test.pred + s * hi))
    return pd.concat(out, ignore_index=True)


def strict_climate(panel: pd.DataFrame, spec: FeatureSpec, years=EXTREME_YEARS) -> pd.DataFrame:
    """Predicción LOYO de `years` con la corrección de sesgo (quantile mapping ERA5→GPM,
    umbrales p95/p90, normal de lluvia) reajustada SIN el año de test: sin ninguna fuga climática."""
    from .features import BiasCorrection, build_features
    daily = pd.read_parquet(DATA_PROCESSED / "climate_daily.parquet")
    wc = pd.read_parquet(DATA_PROCESSED / "worldclim_monthly.parquet")
    meta = pd.read_parquet(DATA_PROCESSED / "area_meta.parquet")
    rows = []
    for yr in years:
        bc = BiasCorrection.fit(daily[daily.date.dt.year != yr], wc, meta)
        feats = build_features(daily, bc)
        p = panel.drop(columns=[c for c in feats.columns if c not in KEY], errors="ignore") \
                 .merge(feats, on=KEY, how="left")
        cv = loyo(p, partial(RidgeModel, spec, feats), spec.columns, years=[yr], value=OUTPUT)
        rows.append(cv[cv.level == "national"])
    return pd.concat(rows, ignore_index=True)


# ── Test de permutación ───────────────────────────────────────────────────────────────
def permutation_test(panel, climate, spec, targets, n: int, seed: int = 0) -> dict:
    """¿La relación clima → producción es real? Se barajan los años del clima (todas las áreas a
    la vez, para conservar su estructura) y se repite la validación: p = fracción de barajados
    con correlación nacional ≥ la observada."""
    feats = [c for c in spec.inputs if c in climate.columns]
    enso = [c for c in spec.inputs if c not in feats]
    enso_by_year = panel.drop_duplicates("year").set_index("year")[enso]
    clim = climate.set_index(KEY)[feats]
    make = partial(RidgeModel, spec, None)       # normal climática desde las filas de entrenamiento

    def stat(p):
        cv = loyo(p, make, spec.columns, value=OUTPUT, targets=targets)
        nat = cv[cv.level == "national"]
        return float(nat.y_cv.corr(nat.pred)) if nat.pred.std() > 0 else 0.0

    obs = stat(panel)
    rng = np.random.default_rng(seed)
    years = np.array(sorted(panel.year.unique()))
    null = []
    for _ in range(n):
        src = panel.year.map(dict(zip(years, rng.permutation(years))))
        p = panel.drop(columns=spec.inputs)
        p[feats] = clim.reindex(pd.MultiIndex.from_arrays([p.area_name, src])).to_numpy()
        if enso:
            p[enso] = enso_by_year.reindex(src).to_numpy()
        null.append(stat(p))
    null = np.array(null)
    return {"n_permutations": n, "corr_national_observed": obs,
            "corr_null_mean": float(null.mean()), "corr_null_p95": float(np.quantile(null, 0.95)),
            "p_value": float((1 + (null >= obs).sum()) / (n + 1))}


# ── Principal ─────────────────────────────────────────────────────────────────────────
def run(perm: int = 0, save: bool = True, verbose: bool = True) -> dict:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    panel, climate = load_data()
    say = print if verbose else (lambda *a, **k: None)
    targets = fold_targets(panel, value=OUTPUT)
    cv_of = partial(loyo, panel, value=OUTPUT, targets=targets)

    # 1. Comparación de modelos -------------------------------------------------------
    cvs = {
        "base_normal": cv_of(Zero, ["rain_anom_pct"]),
        "base_oni": cv_of(OniBaseline, ["is_nino"]),
        "base_lluvia_extrema": cv_of(NinoBaseline, ["rain_anom_pct"]),
        "base_escalon_extremo": cv_of(ExtremeStep, ["rain_anom_pct"]),
        "ridge": cv_of(partial(RidgeModel, CORE, climate), CORE.columns),
        "gbr": cv_of(partial(QuantileGBR, CORE, climate), CORE.columns),
    }
    cvs["ensamble"], w_year = nested_ensemble(cvs["ridge"], cvs["gbr"])
    both = cvs["ridge"].rename(columns={"pred": "ridge"}).merge(
        cvs["gbr"][KEY + ["pred"]].rename(columns={"pred": "gbr"}), on=KEY)
    w_final = best_weight(both)
    cvs["ensamble"] = add_conformal(cvs["ensamble"])
    # Modelo final = Ridge (el ensamble no lo mejora y el GBR no es monótono con pérdida
    # cuantílica); su intervalo es el conformal de sus propios residuos.
    cvs["ridge"] = add_conformal(cvs["ridge"])

    table_of = by_level
    table = {k: by_level(v) for k, v in cvs.items()}
    say("\nValidación leave-one-year-out (anomalía de producción/rendimiento, puntos %)")
    for lvl in ("national", "province"):
        say(f"\n  {lvl}")
        say(pd.DataFrame({k: t[lvl] for k, t in table.items()}).T[
            ["n", "mae", "rmse", "corr", "r2_oos"]].round(2).to_string())
    say(f"\nPeso del ensamble: w = {w_final} (ridge) · elegido por año: "
        f"{w_year.value_counts().sort_index().to_dict()} → modelo final: Ridge")
    ens = cvs["ridge"]
    bases = ("base_normal", "base_oni", "base_lluvia_extrema", "base_escalon_extremo")
    skills = {b: {lvl: skill(ens, cvs[b], lvl) for lvl in ("national", "province")} for b in bases}
    say("Skill del Ridge (1 − error/error_base) nacional:",
        {b: {k: round(v, 2) for k, v in s["national"].items()} for b, s in skills.items()})
    # Ancho del intervalo frente al de "año normal" con el mismo método: ¿informa algo?
    zero_int = add_conformal(cvs["base_normal"])
    width_vs_normal = {lvl: score(ens[ens.level == lvl])["interval_width"]
                       / score(zero_int[zero_int.level == lvl])["interval_width"]
                       for lvl in ("national", "province")}
    say("Intervalo p10–p90 (conformal):",
        {l: {k: round(v, 2) for k, v in t.items() if k in ("coverage_80", "interval_width")}
         for l, t in table_of(ens).items()}, "· ancho / ancho 'año normal':",
        {k: round(v, 2) for k, v in width_vs_normal.items()})

    # 2. Robustez (solo Ridge: es el que decide) ------------------------------------
    def spec_with(**kw):
        return FeatureSpec(**{**dict(anom=CORE.anom, raw=CORE.raw, hinges=CORE.hinges,
                                     signs=CORE.signs), **kw})

    nat_panel = panel[panel.level == "national"]
    yld = panel.assign(**{OUTPUT: panel.yield_t_ha})
    prod_only = panel.assign(**{OUTPUT: np.where(panel.level == "national", panel.production_t,
                                                 panel.yield_t_ha)})
    robust = {
        "bloques_3_anios": loyo(panel, partial(RidgeModel, CORE, climate), CORE.columns,
                                value=OUTPUT, block=3),
        "umbral_1.5sd": cv_of(partial(RidgeModel, spec_with(hinges=(("rain_total", 1.5),)), climate),
                              CORE.columns),
        "umbral_2.5sd": cv_of(partial(RidgeModel, spec_with(hinges=(("rain_total", 2.5),)), climate),
                              CORE.columns),
        "sin_umbral": cv_of(partial(RidgeModel, spec_with(hinges=()), climate), CORE.columns),
        "sin_signos": cv_of(partial(RidgeModel, CORE, climate, True, False), CORE.columns),
        "sin_pesos": cv_of(partial(RidgeModel, CORE, climate, False), CORE.columns),
        "solo_nacional": loyo(nat_panel, partial(RidgeModel, CORE, climate), CORE.columns, value=OUTPUT),
        "target_rendimiento": loyo(yld, partial(RidgeModel, CORE, climate), CORE.columns, value=OUTPUT),
        "target_solo_produccion": loyo(prod_only, partial(RidgeModel, CORE, climate), CORE.columns,
                                       value=OUTPUT),
    }
    rob = {k: score(v[v.level == "national"]) for k, v in robust.items()}
    nat_cv = ens[ens.level == "national"]
    rob["eval_sin_1983_1998"] = score(nat_cv[~nat_cv.year.isin(EXTREME_YEARS)])
    rob["eval_desde_1999"] = score(nat_cv[nat_cv.year >= 1999])
    zero_nat = cvs["base_normal"][cvs["base_normal"].level == "national"]
    for k, yrs in (("eval_sin_1983_1998", ~zero_nat.year.isin(EXTREME_YEARS)),
                   ("eval_desde_1999", zero_nat.year >= 1999)):
        rob[k]["mae_base_normal"] = score(zero_nat[yrs])["mae"]
        rob[k]["rmse_base_normal"] = score(zero_nat[yrs])["rmse"]
    # Prueba justa del target combinado: ¿predice mejor la PRODUCCIÓN sola (lo que importa)?
    t_prod = fold_targets(prod_only[prod_only.level == "national"], value=OUTPUT)
    y_prod = {yr: float(t.set_index("year")[TARGET][yr]) for yr, t in t_prod.items()}
    for k, cvk in (("eval_vs_produccion", ens), ("eval_vs_produccion_entrenado_produccion",
                                                 robust["target_solo_produccion"])):
        n = cvk[cvk.level == "national"].assign(y_cv=lambda d: d.year.map(y_prod)).dropna(subset=["y_cv"])
        rob[k] = score(n.drop(columns=[c for c in ("p10", "p90") if c in n]))
    no_ext = panel[~panel.year.isin(EXTREME_YEARS)]
    # Prueba justa del target combinado: ¿predice mejor la PRODUCCIÓN sola (lo que importa)?
    t_prod = fold_targets(prod_only[prod_only.level == "national"], value=OUTPUT)
    y_prod = {yr: float(t.set_index("year")[TARGET][yr]) for yr, t in t_prod.items()}
    for k, cvk in (("eval_vs_produccion", ens), ("eval_vs_produccion_entrenado_produccion",
                                                 robust["target_solo_produccion"])):
        n = cvk[cvk.level == "national"].assign(y_cv=lambda d: d.year.map(y_prod)).dropna(subset=["y_cv"])
        rob[k] = score(n.drop(columns=[c for c in ("p10", "p90") if c in n]))
    no_ext = panel[~panel.year.isin(EXTREME_YEARS)]
    nat_ext = panel[(panel.level == "national") & panel.year.isin(EXTREME_YEARS)]
    pred_ne = RidgeModel(CORE, climate).fit(no_ext[CORE.columns], no_ext[TARGET]).predict(nat_ext[CORE.columns])
    rob["entrenado_sin_1983_1998"] = {str(int(y)): float(p) for y, p in zip(nat_ext.year, pred_ne)}
    strict = strict_climate(panel, CORE)
    rob["clima_estricto_extremos"] = {str(int(r.year)): float(r.pred) for r in strict.itertuples()}
    say("\nRobustez (Ridge, serie nacional):")
    say(pd.DataFrame({k: v for k, v in rob.items() if "mae" in v}).T[
        ["n", "mae", "rmse", "corr", "r2_oos"]].round(2).to_string())
    say("  (sin 1983/1998 y desde 1999, MAE/RMSE de 'año normal':",
        {k: (round(rob[k]["mae_base_normal"], 2), round(rob[k]["rmse_base_normal"], 2))
         for k in ("eval_sin_1983_1998", "eval_desde_1999")}, ")")
    say("  1983/1998 entrenando sin ambos:", {k: round(v, 1) for k, v in rob["entrenado_sin_1983_1998"].items()},
        "· con corrección climática sin el año:", {k: round(v, 1) for k, v in rob["clima_estricto_extremos"].items()})

    perm_res = None
    if perm:
        perm_res = permutation_test(panel, climate, CORE, targets, perm)
        say("\nTest de permutación:", {k: round(v, 3) for k, v in perm_res.items()})

    # 3. Modelo final ----------------------------------------------------------------
    cols = CORE.columns
    train = panel.dropna(subset=cols + [TARGET])
    final = RidgeModel(CORE, climate).fit(train[cols], train[TARGET])
    scale = _area_scale(ens)
    resid_q = level_q(ens, scale)
    model = CacaoLossModel(
        model=final, resid_q=resid_q, noise_scale=scale.round(3).to_dict(),
        default_scale=float(scale.drop("national").median()), version=VERSION,
        meta={"trained": date.today().isoformat(), "years": [int(train.year.min()), int(train.year.max())]})

    ridge = final
    coef = ridge.coefficients()
    say("\nCoeficientes Ridge (puntos % por desviación estándar):", coef.round(2).to_dict(),
        f"· λ = {ridge.alpha_:.1f}")
    nat = ens[ens.level == "national"].set_index("year")
    events = nat.loc[[y for y in EVENT_YEARS if y in nat.index], ["y_cv", "pred", "p10", "p90"]].round(1)
    say("\nAños de El Niño (nacional, predicción sin haber visto el año):")
    say(events.T.to_string())

    card = {
        "model": "cacao_loss", "version": VERSION, "trained": date.today().isoformat(),
        "question": "Anomalía (%) de la producción de cacao de un área respecto a su tendencia, "
                    "según el clima de la época lluviosa (ene–jun). pérdida % = max(0, −anomalía).",
        "data": {
            "rows": int(len(train)), "areas": sorted(train.area_name.unique()),
            "excluded_areas": EXCLUDE_AREAS, "years": [int(train.year.min()), int(train.year.max())],
            "target_output_by_level": OUTPUT_BY_LEVEL,
            "panel_sha256": hashlib.sha256(
                (DATA_PROCESSED / "training_panel.parquet").read_bytes()).hexdigest(),
        },
        "features": {"inputs": CORE.inputs, "area_anomaly": list(CORE.anom), "raw": list(CORE.raw),
                     "hinges": [list(h) for h in CORE.hinges], "signs": dict(CORE.signs),
                     "factor_groups": FACTOR_GROUPS},
        "formula": {
            "target": "y = 100·(R − T)/T ; T = tendencia LOWESS de log R sin el propio año",
            "prediction": "ŷ = b0 + Σ_k coef_k · (clip(t_k, t_min_k, t_max_k) − center_k) / scale_k",
            "terms": "t_k = (x_k − μ_a,k)/σ_a,k para 'area_anomaly' (normal 1991–2020 del área); "
                     "t_k = max(0, t_x − umbral) para 'hinges' (umbral en desviaciones estándar)",
            "loss": "pérdida % = min(100, max(0, −ŷ))",
            "interval": "[p10, p90] = ŷ + s_a · [q10, q90]_nivel",
            "t_min": ridge.pre_.lo_.round(4).to_dict(), "t_max": ridge.pre_.hi_.round(4).to_dict(), "lambda": ridge.alpha_, "b0": ridge.intercept_,
            "coef": coef.round(4).to_dict(),
            "center": dict(zip(ridge.cols_, np.round(ridge.scaler_.mean_, 4))),
            "scale": dict(zip(ridge.cols_, np.round(ridge.scaler_.scale_, 4))),
            "area_normal_mean": ridge.pre_.mean_.round(4).to_dict("index"),
            "area_normal_sd": ridge.pre_.sd_.round(4).to_dict("index"),
            "q10_q90_by_level": {k: list(v) for k, v in resid_q.items()}, "noise_scale_s_a": model.noise_scale,
            "default_noise_scale": model.default_scale,
        },
        "validation": {
            "method": "leave-one-year-out: el año de test sale del entrenamiento, de la tendencia "
                      "del target y de la normal climática; todas las áreas de ese año a la vez",
            "models": table, "final_model": "ridge", "ensemble_weight_full": w_final,
            "ridge_skill_vs_baselines": skills, "interval_width_vs_normal": width_vs_normal,
            "ensemble_weight_by_test_year": {str(k): int(v) for k, v in
                                             w_year.value_counts().sort_index().items()},
            "robustness_ridge_national": rob, "permutation_test": perm_res,
            "nino_events_national": events.reset_index().to_dict("records"),
        },
        "limits": [
            "La señal validada es NACIONAL y es un detector de lluvia extrema: depende casi por "
            "completo de 1983 y 1998 (lluvia ene–jun > 3.5 desviaciones). Sin esos dos años la "
            "correlación cae a ~0.3 y el MAE no mejora a 'año normal' (ver eval_sin_1983_1998).",
            "Hacia atrás no se aprende: cada Niño extremo se predice gracias al otro "
            "(entrenado_sin_1983_1998). Un tercer evento extremo podría comportarse distinto.",
            "A nivel de provincia el modelo NO supera a predecir 'año normal' (ruido ESPAC 15–31 %). "
            "La salida por zona aplica la respuesta nacional al clima local: evidence = "
            "'indice_subnacional_no_validado'.",
            "No extrapola: cada término se recorta al rango de entrenamiento (extrapolated = True). "
            "La pérdida se acota a [0, 100] %.",
            "El índice Niño 1+2 no aporta una vez conocida la lluvia local: el modelo no sirve para "
            "un escenario 'solo ENSO'; hace falta el clima (observado o pronosticado) de ene–jun.",
            "El intervalo p10–p90 cubre ~80 % en promedio pero casi no es más estrecho que el de "
            "'año normal' (interval_width_vs_normal); en años de pérdida grande cubre peor.",
            "Target nacional = media geométrica de producción y exportaciones (FAOSTAT): reduce el "
            "error de medición. Contra la producción sola la mejora es pequeña (eval_vs_produccion "
            "frente a eval_vs_produccion_entrenado_produccion).",
            "Decisiones tomadas viendo los datos (target producción, umbral, signos, variables): "
            "eligiéndolas dentro de cada pliegue la correlación queda en 0.50–0.56 (auditoría).",
            "La corrección de sesgo climática (quantile mapping, normal 1991–2020) incluye el año "
            "de test; reajustada sin él cambia 1998 unos puntos (clima_estricto_extremos).",
        ],
    }
    if save:
        ARTIFACTS.mkdir(exist_ok=True)
        clim = load_climate()
        years = scenario_years(clim)
        sf = scenario_features(clim, CORE.inputs, years)
        bundle = build_bundle(model, train, clim, sf, years, card["validation"])
        joblib.dump(bundle, ARTIFACTS / f"cacao_loss_{VERSION}.joblib")
        (ARTIFACTS / f"model_card_{VERSION}.json").write_text(
            json.dumps(card, indent=2, ensure_ascii=False, default=float))
        out = ens.merge(cvs["ridge"][KEY + ["pred"]].rename(columns={"pred": "pred_ridge"}), on=KEY) \
                 .merge(cvs["gbr"][KEY + ["pred"]].rename(columns={"pred": "pred_gbr"}), on=KEY)
        out.round(2).to_csv(ARTIFACTS / f"cv_predictions_{VERSION}.csv", index=False)
        say(f"\nGuardado: {ARTIFACTS / f'cacao_loss_{VERSION}.joblib'} (+ model_card, cv_predictions)")
    return {"model": model, "card": card, "cvs": cvs, "panel": panel, "climate": climate}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perm", type=int, default=0, help="nº de permutaciones (0 = no hacer el test)")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    run(perm=a.perm, save=not a.no_save)


if __name__ == "__main__":
    main()
