"""Fase 4: el modelo real (ml.model) y su entrenamiento (ml.train).

Tres bloques:
  1. El modelo recupera la verdad en datos sintéticos y no inventa señal donde no la hay.
  2. Guardas contra fugas: normal climática, peso del ensamble e intervalos sin el año de test.
  3. El artefacto entrenado con datos reales cumple el contrato que usará la API.
"""
import json
from functools import partial

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.config import ARTIFACTS, DATA_PROCESSED
from ml.dataset import TARGET, add_target
from ml.model import (CLIMATE_CORE as CORE, CacaoLossModel, FeatureSpec, Preprocessor, QuantileGBR,
                      RidgeModel, hinge_name, risk_class)
from ml.synthetic import Truth, make_panel
from ml.train import VERSION, add_conformal, best_weight, nested_ensemble, score
from ml.validation import NinoBaseline, fold_targets, loyo, metrics

AREAS = ["national", "Los Rios", "Guayas", "Manabi"]
COLS = CORE.columns


@pytest.fixture(scope="module")
def nonlinear():
    return add_target(make_panel(Truth(), areas=AREAS, seed=2, extreme_years=5))


@pytest.fixture(scope="module")
def targets(nonlinear):
    return fold_targets(nonlinear)                 # lo lento (LOWESS por pliegue), una sola vez


@pytest.fixture(scope="module")
def cv_ridge(nonlinear, targets):
    return loyo(nonlinear, partial(RidgeModel, CORE), COLS, targets=targets)


# ── 1. Recupera la verdad sintética ───────────────────────────────────────────────────
def test_ridge_recovers_synthetic_truth(nonlinear, cv_ridge, targets):
    base = loyo(nonlinear, NinoBaseline, ["rain_anom_pct"], targets=targets)
    m = metrics(cv_ridge, base)
    assert m["skill"] > 0.15 and m["corr"] > 0.8
    wet = cv_ridge.merge(nonlinear[["area_name", "year", "rain_anom_pct"]]).rain_anom_pct > 100
    assert cv_ridge.pred[wet].mean() < -15                      # años extremos → pérdida grande


def test_ridge_coefficients_respect_physical_signs(nonlinear):
    df = nonlinear.dropna(subset=[TARGET])
    c = RidgeModel(CORE).fit(df[COLS], df[TARGET]).coefficients()
    for col, sign in CORE.signs:
        assert c[col] * sign >= 0, col
    assert c[hinge_name("rain_total", 2.0)] < 0             # el umbral existe en la verdad
    # humedad: variables muy correlacionadas → se comprueba el grupo, no cada coeficiente
    assert c["fav_days_phytophthora"] + c["saturated_days"] < -4


def test_null_truth_has_no_skill():
    """Sin efecto del clima, el modelo real tampoco debe mostrar skill (si lo muestra, hay fuga)."""
    panel = add_target(make_panel(Truth.null(), areas=AREAS, seed=5))
    cv = loyo(panel, partial(RidgeModel, CORE), COLS)
    assert abs(cv.y_cv.corr(cv.pred)) < 0.2
    assert score(cv)["r2_oos"] < 0.03


def test_gbr_quantiles_are_ordered(nonlinear):
    """El GBR (solo comparación) devuelve p10 ≤ p50 ≤ p90. Su monotonía NO está garantizada
    con pérdida cuantílica en scikit-learn: por eso el modelo final es el Ridge."""
    df = nonlinear.dropna(subset=[TARGET])
    m = QuantileGBR(CORE, n_estimators=60).fit(df[COLS], df[TARGET])
    lo, mid, hi = m.predict_quantiles(df[COLS].iloc[:30])
    assert np.all(lo <= mid) and np.all(mid <= hi)


def test_ridge_is_monotone_in_rain(nonlinear):
    df = nonlinear.dropna(subset=[TARGET])
    m = RidgeModel(CORE).fit(df[COLS], df[TARGET])
    row = df[COLS].iloc[[0]]
    grid = pd.concat([row.assign(rain_total=r) for r in np.linspace(df.rain_total.min(),
                                                                       df.rain_total.max(), 50)])
    assert np.all(np.diff(m.predict(grid)) <= 1e-9)             # más lluvia nunca sube la predicción


def test_ridge_does_not_extrapolate(nonlinear):
    """Más allá del clima más extremo visto, la predicción se queda en la de ese extremo."""
    df = nonlinear.dropna(subset=[TARGET])
    top = df.rain_total.max()
    row = df[df.rain_total == top][COLS].iloc[[0]]
    grid = pd.concat([row, row.assign(rain_total=top * 3), row.assign(rain_total=top * 5)])
    m = RidgeModel(CORE).fit(df[COLS], df[TARGET])
    p = m.predict(grid)
    assert p[2] == pytest.approx(p[1]) and p[1] <= p[0]
    assert m.pre_.extrapolated(grid).tolist() == [False, True, True]


# ── 2. Guardas contra fugas ───────────────────────────────────────────────────────────
def test_climate_normal_ignores_years_outside_training():
    """La normal del área solo usa años presentes en el entrenamiento."""
    years = np.arange(1991, 2021)
    clim = pd.DataFrame({"area_name": "a", "year": years, "x": np.linspace(0, 29, 30)})
    spec = FeatureSpec(anom=("x",))
    X = clim[clim.year != 2000]
    ref = Preprocessor(spec, clim).fit(X)
    wild = clim.assign(x=clim.x.where(clim.year != 2000, 1e6))    # el año de test cambia…
    alt = Preprocessor(spec, wild).fit(X)
    assert ref.mean_.x.a == alt.mean_.x.a and ref.sd_.x.a == alt.sd_.x.a   # …y la normal no


def test_block_loyo_holds_out_neighbour_years(nonlinear):
    seen = {}

    class Spy:
        def fit(self, X, y):
            self.years = set(X.year)
            return self

        def predict(self, X):
            seen[int(X.year.iloc[0])] = self.years
            return np.zeros(len(X))

    loyo(nonlinear, Spy, COLS, years=[1990], block=3)
    assert not {1989, 1990, 1991} & seen[1990] and {1988, 1992} <= seen[1990]


def test_nested_ensemble_weight_does_not_see_test_year():
    """Cambiar el resultado de un año no cambia el peso con el que se predice ESE año."""
    rng = np.random.default_rng(0)
    n = 40
    y = rng.normal(0, 10, n)
    base = pd.DataFrame({"area_name": "a", "year": np.arange(n), "level": "national", "y_cv": y})
    ridge = base.assign(pred=y + rng.normal(0, 3, n))
    gbr = base.assign(pred=y + rng.normal(0, 9, n))
    _, w = nested_ensemble(ridge, gbr)
    r2, g2 = ridge.copy(), gbr.copy()
    r2.loc[5, "pred"], g2.loc[5, "pred"] = 500.0, y[5]              # en el año 5 el GBR "acierta"
    _, w2 = nested_ensemble(r2, g2)
    assert w2[5] == w[5]
    assert best_weight(ridge.rename(columns={"pred": "ridge"}).assign(gbr=gbr.pred)) >= 0.75


def test_conformal_interval_covers_about_80_percent(cv_ridge):
    cv = add_conformal(cv_ridge)
    cover = ((cv.y_cv >= cv.p10) & (cv.y_cv <= cv.p90)).mean()
    assert 0.74 <= cover <= 0.88
    # el intervalo de un año no depende del resultado de ese año ni de sus vecinos de tendencia
    alt = cv_ridge.copy()
    alt.loc[alt.year.between(1984, 1996), "y_cv"] += 500
    a = add_conformal(alt)
    k = cv.year == 1990
    assert np.allclose(a[a.year == 1990][["p10", "p90"]], cv[k][["p10", "p90"]])


# ── 3. Contrato del artefacto ─────────────────────────────────────────────────────────
def test_prediction_ignores_test_year_output(nonlinear):
    """Extremo a extremo: multiplicar la producción del año de test no cambia su predicción."""
    p = nonlinear.copy()
    p.loc[p.year == 1990, "yield_t_ha"] *= 10
    a = loyo(nonlinear, partial(RidgeModel, CORE), COLS, years=[1990])
    b = loyo(p, partial(RidgeModel, CORE), COLS, years=[1990])
    assert np.allclose(a.pred, b.pred) and not np.allclose(a.y_cv, b.y_cv)


def _toy_model(nonlinear) -> CacaoLossModel:
    df = nonlinear.dropna(subset=[TARGET])
    m = RidgeModel(CORE).fit(df[COLS], df[TARGET])
    q = {"national": (-1.2, 1.3), "province": (-1.0, 1.1)}
    return CacaoLossModel(m, q, {a: 10.0 for a in AREAS}, 12.0, "test")


def test_predict_contract_and_roundtrip(nonlinear, tmp_path):
    model = _toy_model(nonlinear)
    X = nonlinear[COLS].groupby("area_name").head(2)
    out = model.predict(X)
    assert list(out.columns) == ["area_name", "year", "y_anom_pct", "y_anom_p10", "y_anom_p90",
                                 "loss_pct", "loss_p10", "loss_p90", "risk_class", "top_factors",
                                 "extrapolated", "evidence", "model_version"]
    assert set(out.evidence) == {"validado_nacional", "indice_subnacional_no_validado"}
    assert (out.loss_pct >= 0).all() and (out.loss_p10 <= out.loss_pct).all()
    assert (out.loss_pct <= out.loss_p90).all() and (out.y_anom_p10 <= out.y_anom_p90).all()
    assert out.loss_pct.equals((-out.y_anom_pct).clip(0, 100))
    f = out.top_factors.iloc[0]
    assert len(f) == 3 and set(f[0]) == {"name", "contribution"}
    json.dumps(out.to_dict("records"))                           # serializable para la API
    # las contribuciones suman la predicción (menos la constante)
    c = model.model.contributions(X)
    assert np.allclose(np.diff(c.sum(axis=1) - model.model.predict(X)), 0, atol=1e-6)
    # se guarda sin la tabla climática y predice igual al recargar
    joblib.dump(model, tmp_path / "m.joblib")
    again = joblib.load(tmp_path / "m.joblib").predict(X)
    assert np.allclose(again.y_anom_pct, out.y_anom_pct)


def test_new_area_needs_climate_normal(nonlinear):
    model = _toy_model(nonlinear)
    X = nonlinear[COLS].iloc[:3].assign(area_name="Vinces")
    with pytest.raises(KeyError):
        model.predict(X)
    hist = nonlinear[nonlinear.area_name == "Los Rios"]
    model.model.pre_.add_area("Vinces", hist)                    # normal del cantón nuevo
    assert len(model.predict(X)) == 3


def test_loss_capped_at_100(nonlinear):
    model = _toy_model(nonlinear)
    model.model.intercept_ = -500.0                              # fuerza una anomalía absurda
    out = model.predict(nonlinear[COLS].iloc[:4])
    assert (out.loss_pct == 100).all() and (out.loss_p90 <= 100).all()


def test_risk_classes():
    assert [risk_class(v) for v in (0, 4.9, 5, 14.9, 15, 29.9, 30, 80)] == [
        "bajo", "bajo", "medio", "medio", "alto", "alto", "muy_alto", "muy_alto"]


@pytest.fixture(scope="module")
def trained():
    path = ARTIFACTS / f"cacao_loss_{VERSION}.joblib"
    if not path.exists():
        pytest.skip("modelo no entrenado: ml/.venv/bin/python -m ml.train")
    card = json.loads((ARTIFACTS / f"model_card_{VERSION}.json").read_text())
    return joblib.load(path)["model"], card


def test_trained_model_validation_metrics(trained):
    """Lo que el modelo real demuestra (y lo que no) en validación fuera de muestra."""
    _, card = trained
    v = card["validation"]
    assert v["final_model"] == "ridge"
    nat, base = v["models"]["ridge"]["national"], v["models"]["base_normal"]["national"]
    assert nat["corr"] > 0.4 and nat["r2_oos"] > 0.15            # hay señal nacional
    assert nat["rmse"] < base["rmse"] and nat["mae"] < base["mae"]
    assert nat["rmse"] < v["models"]["base_lluvia_extrema"]["national"]["rmse"]
    assert 0.7 <= nat["coverage_80"] <= 0.9
    assert 0.65 <= v["models"]["ridge"]["province"]["coverage_80"] <= 0.9
    # sin los dos Niños extremos la señal es pequeña: la model card debe decirlo
    rob = v["robustness_ridge_national"]
    assert rob["eval_sin_1983_1998"]["corr"] < nat["corr"]
    assert rob["clima_estricto_extremos"]["1998"] < -15
    assert v["robustness_ridge_national"]["bloques_3_anios"]["corr"] > 0.35
    ev = {e["year"]: e for e in v["nino_events_national"]}
    assert ev[1983]["pred"] < -20 and ev[1998]["pred"] < -20     # anticipa los dos Niños extremos
    if v["permutation_test"]:
        assert v["permutation_test"]["national"]["p_value"] < 0.05
        assert v["permutation_test"]["province"]["p_value"] < 0.05


def test_trained_model_scenarios(trained):
    """Un Niño extremo como 1998 da pérdida alta; un año normal, pérdida baja."""
    model, card = trained
    panel = pd.read_parquet(DATA_PROCESSED / "training_panel.parquet")
    nat = panel[panel.area_name == "national"]
    out = model.predict(nat[nat.year.isin([1998, 2015])][model.model.spec.columns]).set_index("year")
    assert out.evidence[1998] == "validado_nacional"
    assert out.loss_pct[1998] > 25 and out.risk_class[1998] in ("alto", "muy_alto")
    assert out.loss_pct[2015] < 10
    assert out.top_factors[1998][0]["contribution"] < 0
    # la model card reproduce la predicción solo con sus números (para usarla fuera de Python)
    f = card["formula"]
    row = nat[nat.year == 1998].iloc[0]
    y = f["b0"]
    t = {}
    for k in f["coef"]:
        if k in f["area_normal_mean"]["national"]:
            t[k] = (row[k] - f["area_normal_mean"]["national"][k]) / f["area_normal_sd"]["national"][k]
            if np.isnan(t[k]):                                   # MODIS sin dato → anomalía 0
                t[k] = 0.0
    for k in f["coef"]:
        if "_gt" in k:
            col, knot = k.rsplit("_gt", 1)
            t[k] = max(0.0, t[col] - float(knot))
    for k, coef in f["coef"].items():
        tk = min(max(t[k], f["t_min"][k]), f["t_max"][k])
        y += coef * (tk - f["center"][k]) / f["scale"][k]
    assert y == pytest.approx(out.y_anom_pct[1998], abs=0.05)
