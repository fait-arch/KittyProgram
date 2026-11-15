"""Proyecciones 2026–2050 de la pérdida de cacao (NASA NEX-GDDP-CMIP6, método delta).

    ml/.venv/bin/python -m ml.etl.cmip6          # medias mensuales CMIP6 por área (GEE)
    ml/.venv/bin/python -m ml.projections        # → artifacts/projections_v1.csv + escenarios ssp*_2050

1. Cambio climático de cada mes (por área y modelo climático), para el año Y:
       ΔT  = media(Y−10 … Y+10) − media(1995–2014)          (tas, tasmax, tasmin; °C)
       ΔHR = ídem para hurs (puntos %)
       rP  = media(Y−10 … Y+10) / media(1995–2014)          (lluvia; acotado a 0.5–2)
   La ventana de 21 años quita el ruido de un año suelto; restar el histórico DEL MISMO modelo
   cancela su sesgo.
2. Se aplica al clima diario OBSERVADO (ya corregido) de los años base:
       T' = T + ΔT ;  HR' = clip(HR + ΔHR) → Td' (Magnus inverso) ;  P' = P · rP
   y se recalculan las features con las mismas fórmulas (ml.features). Suelo saturado y radiación
   no tienen delta directo: se ajustan con la pendiente histórica del área frente a la lluvia
   (las mismas sensibilidades del what-if). El verdor (EVI) y el precio quedan en "normal".
3. Años base: 1991–2020 (año típico) y 1983 + 1998 (un Niño extremo con el clima de ese año).
   Pérdida del año Y = media de las pérdidas de los años base. Se calcula en 2026, 2030, 2035,
   2040, 2045 y 2050 y se interpola linealmente para los años intermedios (el delta es suave).
4. Ensamble = media de los 4 modelos climáticos; rango = mínimo–máximo entre modelos.
5. Pérdida anual esperada (lo que el método delta NO capta: cuántos Niños extremos habrá):
       E[pérdida] = (1 − p)·pérdida_típica + p·pérdida_Niño_extremo
   p_hoy = 2/65 (1983 y 1998 en 1961–2025). Escenario "frecuencia ×2": Cai et al. (2014, Nature
   Climate Change 4:111–116) proyectan que los Niños extremos pasan de ~1 cada 20 años a ~1 cada 10
   con el calentamiento; aquí p sube linealmente de p_hoy (2025) a 2·p_hoy (2050).

Limitación (también en la salida): el modelo se entrenó con el clima observado; el clima futuro
puede salir del rango de entrenamiento (`extrapolated = True`), y el modelo NO extrapola: recorta
cada término al rango visto, así que la pérdida futura puede estar subestimada.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .cantons_predict import canton_bias
from .config import ARTIFACTS, DATA_PROCESSED, ROOT
from .features import RAINY_MONTHS, add_daily_derived, sat_vapor_pressure, yearly_features
from .model import ID_COLS, NON_CLIMATE, risk_class
from .predict import VERSION, load_bundle

KEY_YEARS = [2026, 2030, 2035, 2040, 2045, 2050]
BASES = {"tipico": list(range(1991, 2021)), "nino_extremo": [1983, 1998]}
SSPS = ["ssp245", "ssp585"]
HIST = (1995, 2014)
OUT = ARTIFACTS / f"projections_{VERSION}"


def monthly_deltas() -> pd.DataFrame:
    """area_name, model, ssp, year, month → dT, dTmax, dTmin, dHR, rP."""
    c = pd.read_parquet(DATA_PROCESSED / "cmip6_monthly.parquet")
    hist = c[(c.scenario == "historical") & c.year.between(*HIST)].groupby(["area_name", "model", "month"])[
        ["tas", "tasmax", "tasmin", "hurs", "pr"]].mean()
    rows = []
    for ssp in SSPS:
        f = c[c.scenario == ssp]
        for y in KEY_YEARS:
            w = f[f.year.between(y - 10, y + 10)].groupby(["area_name", "model", "month"])[
                ["tas", "tasmax", "tasmin", "hurs", "pr"]].mean()
            d = pd.DataFrame({"dT": w.tas - hist.tas, "dTmax": w.tasmax - hist.tasmax, "dTmin": w.tasmin - hist.tasmin,
                              "dHR": w.hurs - hist.hurs, "rP": (w.pr / hist.pr).clip(0.5, 2.0)}).reset_index()
            rows.append(d.assign(ssp=ssp, year=y))
    return pd.concat(rows, ignore_index=True)


def _dewpoint(t_c, rh):
    """Td desde T y HR (inverso de e° de FAO-56)."""
    e = sat_vapor_pressure(t_c) * np.clip(rh, 1, 100) / 100
    a = np.log(e / 0.6108)
    return 237.3 * a / (17.27 - a)


def future_features(corrected: pd.DataFrame, bc, delta: pd.DataFrame) -> pd.DataFrame:
    """Clima diario corregido + delta mensual por área → features anuales futuras."""
    d = corrected.copy()
    dm = d[["area_name"]].assign(month=d.date.dt.month.to_numpy()).merge(
        delta, on=["area_name", "month"], how="left").fillna({"dT": 0, "dTmax": 0, "dTmin": 0, "dHR": 0, "rP": 1})
    month = d.date.dt.month.to_numpy()
    td_shift = np.fromiter((bc.temp_delta[a]["t2m_c"][m] for a, m in zip(d.area_name, month)), float, len(d))
    rh0 = 100 * sat_vapor_pressure(d.dewpoint_c + td_shift) / sat_vapor_pressure(d.t2m_c)
    d["t2m_c"] = d.t2m_c + dm.dT.to_numpy()
    d["t2m_max_c"] = d.t2m_max_c + dm.dTmax.to_numpy()
    d["t2m_min_c"] = d.t2m_min_c + dm.dTmin.to_numpy()
    rh1 = np.clip(np.clip(rh0, 0, 100) + dm.dHR.to_numpy(), 1, 100)
    d["dewpoint_c"] = _dewpoint(d.t2m_c.to_numpy(), rh1) - td_shift
    d["precip_mm"] = d.precip_mm * dm.rP.to_numpy()
    return yearly_features(add_daily_derived(d, bc), bc, RAINY_MONTHS)


def adjust_soil_solar(fut: pd.DataFrame, base: pd.DataFrame, sens: dict) -> pd.DataFrame:
    """Suelo saturado y radiación siguen a la lluvia con la pendiente histórica del área."""
    m = fut.merge(base[["area_name", "year", "rain_total", "saturated_days", "solar_mean"]],
                  on=["area_name", "year"], suffixes=("", "_b"))
    s = m.area_name.map(lambda a: sens.get(a) or sens["national"])
    d_rain = m.rain_total - m.rain_total_b
    m["saturated_days"] = np.clip(m.saturated_days_b + s.map(lambda x: x["sat_per_mm"]) * d_rain, 0, 181)
    m["solar_mean"] = np.maximum(0, m.solar_mean_b + s.map(lambda x: x["sol_per_mm"]) * d_rain)
    return m.drop(columns=[c for c in m.columns if c.endswith("_b")])


def project(bundle, corrected, bc, base_feats, deltas, areas, kind) -> pd.DataFrame:
    m = bundle["model"]
    years_all = sorted({y for v in BASES.values() for y in v})
    corrected = corrected[corrected.date.dt.year.isin(years_all) & corrected.date.dt.month.isin(RAINY_MONTHS)
                          & corrected.area_name.isin(areas)]
    rows = []
    for (ssp, model, y), dl in deltas[deltas.area_name.isin(areas)].groupby(["ssp", "model", "year"]):
        fut = future_features(corrected, bc, dl[["area_name", "month", "dT", "dTmax", "dTmin", "dHR", "rP"]])
        fut = adjust_soil_solar(fut, base_feats, bundle["sensitivities"])
        for c in NON_CLIMATE + ("evi_jan_jun",):
            fut[c] = np.nan
        for base, byears in BASES.items():
            X = fut[fut.year.isin(byears)][ID_COLS + m.features]
            if X.empty:
                continue
            out = m.predict(X)
            g = out.groupby("area_name").agg(loss_pct=("loss_pct", "mean"), prob_loss_gt20=("prob_loss_gt20", "mean"),
                                             loss_p10=("loss_p10", "mean"), loss_p90=("loss_p90", "mean"),
                                             extrapolated=("extrapolated", "any"))
            dd = dl.groupby("area_name").agg(dT_ene_jun=("dT", lambda s: s.iloc[:6].mean()),
                                             dP_ene_jun_pct=("rP", lambda s: 100 * (s.iloc[:6].mean() - 1)))
            g = g.join(dd).reset_index().assign(ssp=ssp, model=model, year=y, base=base, kind=kind)
            rows.append(g)
    return pd.concat(rows, ignore_index=True)


def summarize(raw: pd.DataFrame) -> pd.DataFrame:
    """Ensamble de modelos e interpolación anual 2026–2050."""
    keys = ["area_name", "kind", "ssp", "base"]
    ens = raw.groupby(keys + ["year"]).agg(
        loss_pct=("loss_pct", "mean"), loss_pct_min=("loss_pct", "min"), loss_pct_max=("loss_pct", "max"),
        prob_loss_gt20=("prob_loss_gt20", "mean"), extrapolated=("extrapolated", "any"),
        loss_p10=("loss_p10", "mean"), loss_p90=("loss_p90", "mean"),
        dT_ene_jun=("dT_ene_jun", "mean"), dP_ene_jun_pct=("dP_ene_jun_pct", "mean")).reset_index()
    out = []
    for k, g in ens.groupby(keys):
        g = g.set_index("year").reindex(range(KEY_YEARS[0], KEY_YEARS[-1] + 1))
        num = g.select_dtypes("number").columns
        g[num] = g[num].interpolate()
        g["extrapolated"] = g.extrapolated.ffill().astype(bool)
        g[keys] = k
        out.append(g.reset_index())
    res = pd.concat(out, ignore_index=True)
    res["risk_class"] = [risk_class(v) for v in res.loss_pct]
    return res


P_EXT_TODAY = 2 / 65


def baseline_today(bundle, base_feats, areas) -> pd.DataFrame:
    """Misma cuenta sin cambio climático: pérdida media de los años base con el clima observado."""
    m = bundle["model"]
    f = base_feats[base_feats.area_name.isin(areas)].copy()
    for c in NON_CLIMATE + ("evi_jan_jun",):
        f[c] = np.nan
    rows = []
    for base, byears in BASES.items():
        X = f[f.year.isin(byears)][ID_COLS + m.features]
        g = m.predict(X).groupby("area_name").loss_pct.mean().rename("loss_pct_hoy").reset_index()
        rows.append(g.assign(base=base))
    return pd.concat(rows, ignore_index=True)


def expected_annual(res: pd.DataFrame, today: pd.DataFrame) -> pd.DataFrame:
    """Pérdida anual esperada con la frecuencia de Niños extremos de hoy y con frecuencia ×2."""
    w = res.pivot_table(index=["area_name", "ssp", "year"], columns="base", values="loss_pct").reset_index()
    t = today.pivot(index="area_name", columns="base", values="loss_pct_hoy")
    p2 = P_EXT_TODAY * (1 + (w.year - 2025) / 25)
    w["anual_frecuencia_hoy"] = (1 - P_EXT_TODAY) * w.tipico + P_EXT_TODAY * w.nino_extremo
    w["anual_frecuencia_x2"] = (1 - p2) * w.tipico + p2 * w.nino_extremo
    w["anual_hoy"] = w.area_name.map((1 - P_EXT_TODAY) * t.tipico + P_EXT_TODAY * t.nino_extremo)
    return w[["area_name", "ssp", "year", "anual_hoy", "anual_frecuencia_hoy", "anual_frecuencia_x2"]]


def run(verbose=True) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    bundle = load_bundle()
    deltas = monthly_deltas()
    import joblib
    # país y provincias: clima y corrección de sesgo de la Fase 2
    from .dataset import fit_bias_correction
    bc_p, daily_p = fit_bias_correction()
    prov_areas = [a for a in bundle["model"].noise_scale]           # áreas de entrenamiento
    base_p = pd.read_parquet(DATA_PROCESSED / "features_area_year.parquet")
    raw_p = project(bundle, bc_p.apply(daily_p[daily_p.area_name.isin(prov_areas)]), bc_p, base_p, deltas,
                    prov_areas, "national/province")
    # cantones
    daily_c = pd.read_parquet(DATA_PROCESSED / "climate_daily_cantons.parquet")
    meta = pd.read_pickle(DATA_PROCESSED / "canton_meta.pkl")
    meta = meta[meta.area_name.isin(daily_c.area_name.unique())]
    bc_c = canton_bias(daily_c, meta)
    from .cantons_predict import canton_features
    base_c, _ = canton_features()
    cantons = [a for a in meta.area_name if a in bundle["model"].model.pre_.mean_.index]
    raw_c = project(bundle, bc_c.apply(daily_c[daily_c.area_name.isin(cantons)]), bc_c, base_c, deltas,
                    cantons, "canton")
    raw = pd.concat([raw_p, raw_c], ignore_index=True)
    res = summarize(raw)
    today = pd.concat([baseline_today(bundle, base_p, prov_areas), baseline_today(bundle, base_c, cantons)])
    res = res.merge(today, on=["area_name", "base"], how="left").merge(
        expected_annual(res, today), on=["area_name", "ssp", "year"], how="left")
    res["kind"] = np.where(res.kind == "canton", "canton", np.where(res.area_name == "national", "country", "province"))
    cant = pd.read_csv(ROOT / "data" / "cantons_supabase.csv", dtype=str).set_index("id")
    prov = pd.read_csv(ROOT / "data" / "provinces_supabase.csv", dtype=str).dropna(subset=["model_name"]).set_index("model_name")
    res["area_id"] = np.where(res.kind == "canton", res.area_name, res.area_name.map(prov.id))
    res["name"] = np.where(res.kind == "canton", res.area_name.map(cant.name), res.area_name.map(prov.name))
    res["province"] = np.where(res.kind == "canton", res.area_name.map(cant.province),
                               np.where(res.kind == "province", res.area_name.map(prov.name), None))
    raw.to_parquet(f"{OUT}_by_model.parquet", index=False)
    res.round(3).to_parquet(f"{OUT}.parquet", index=False)
    res.round(3).to_csv(f"{OUT}.csv", index=False)
    if verbose:
        n = res[(res.area_name == "national") & res.year.isin(KEY_YEARS)]
        print("Nacional — pérdida esperada (%) [rango entre modelos]:")
        for (ssp, base), g in n.groupby(["ssp", "base"]):
            print(f"  {ssp} {base:12s}", "  ".join(f"{int(r.year)}: {r.loss_pct:.1f} [{r.loss_pct_min:.1f}–{r.loss_pct_max:.1f}]"
                                                  for r in g.itertuples()))
        a = n[n.base == "tipico"].set_index(["ssp", "year"])[["anual_hoy", "anual_frecuencia_hoy", "anual_frecuencia_x2"]]
        print("Pérdida ANUAL esperada nacional (%):"); print(a.round(2).to_string())
        print("Cambio ene–jun 2050 (nacional):", n[n.year == 2050].groupby("ssp")[["dT_ene_jun", "dP_ene_jun_pct"]].first().round(2).to_dict("index"))
        print(f"Guardado: {OUT}.csv/.parquet ({len(res)} filas, {res.area_id.nunique()} áreas)")
    allp = add_2050_scenarios(res)
    if verbose:
        print("Escenarios en loss_predictions_areas:", allp.scenario_id.value_counts().to_dict())
    return res




def add_2050_scenarios(res: pd.DataFrame) -> pd.DataFrame:
    """Escenarios `ssp245_2050` / `ssp585_2050` (año típico 2050, tabla `scenarios` de Supabase) en
    loss_predictions_areas_v1, con la exposición de hoy. Correr después de ml.cantons_predict."""
    path = ARTIFACTS / f"loss_predictions_areas_{VERSION}.parquet"
    cur = pd.read_parquet(path)
    cur = cur[~cur.scenario_id.str.endswith("_2050")]
    ref = cur[cur.scenario_id == "normal"].set_index("area_id")
    p = res[(res.year == 2050) & (res.base == "tipico")]
    rows = []
    for r in p.itertuples():
        if r.area_id not in ref.index:
            continue
        b = ref.loc[r.area_id]
        loss_t = b.exposed_ha * b.expected_yield_t_ha * r.loss_pct / 100 if pd.notna(b.exposed_ha) else None
        rows.append({"area_id": r.area_id, "kind": b.kind, "name": b["name"], "province": b.province,
                     "scenario_id": f"{r.ssp}_2050", "loss_pct": round(r.loss_pct, 2),
                     "loss_pct_low": round(r.loss_p10, 2), "loss_pct_high": round(r.loss_p90, 2),
                     "risk_class": r.risk_class, "prob_loss_gt20": round(r.prob_loss_gt20, 3),
                     "top_factors": "[]", "extrapolated": bool(r.extrapolated),
                     "evidence": "proyeccion_cmip6_no_validada", "scenario_years": "[1991, 2020]",
                     "exposed_ha": b.exposed_ha, "expected_yield_t_ha": b.expected_yield_t_ha,
                     "loss_t": round(loss_t, 1) if loss_t is not None else None, "price_usd_t": b.price_usd_t,
                     "loss_usd": round(loss_t * b.price_usd_t) if loss_t is not None else None,
                     "model_version": b.model_version,
                     "loss_pct_models_min": round(r.loss_pct_min, 2), "loss_pct_models_max": round(r.loss_pct_max, 2),
                     "annual_loss_pct_today": round(r.anual_hoy, 2),
                     "annual_loss_pct_2050_freq_today": round(r.anual_frecuencia_hoy, 2),
                     "annual_loss_pct_2050_freq_x2": round(r.anual_frecuencia_x2, 2)})
    out = pd.concat([cur, pd.DataFrame(rows)], ignore_index=True)
    out.to_parquet(path, index=False)
    out.to_csv(path.with_suffix(".csv"), index=False)
    return out


if __name__ == "__main__":
    import sys
    if "--only-merge" in sys.argv:
        add_2050_scenarios(pd.read_parquet(f"{OUT}.parquet"))
    else:
        run()
