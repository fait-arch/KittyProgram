"""Predicciones por CANTÓN (y provincia/país) con los ids de Supabase.

    ml/.venv/bin/python -m ml.etl.cantons        # una vez: clima diario por cantón (GEE)
    ml/.venv/bin/python -m ml.cantons_predict    # → artifacts/loss_predictions_areas_v1.csv/.parquet

Para cada cantón (126, tabla `areas` de Supabase):
  1. Corrección de sesgo propia. Temperatura: el cantón solo tiene ERA5 desde 1991, así que
         delta_c(mes) = WorldClim_c − ERA5_c(1991–2020) + [ERA5_nac(1991–2020) − ERA5_nac(1961–1990)]
     (el último término devuelve el calentamiento ocurrido desde la normal de WorldClim).
     Lluvia: quantile mapping ERA5 → GPM del propio cantón (1998–2025).
  2. Mismas features que las provincias (ml.features) y normal climática 1991–2020 del cantón
     (`inference.register_area`): el modelo nacional se aplica a su anomalía climática.
  3. Escenarios del bundle (normal, nino, nina, nino_extremo, actual) con los años disponibles.
     1983 no está en la serie de los cantones (empieza en 1991): `nino_extremo` usa 1998.
  4. Exposición: ha sembradas de la provincia (ESPAC, último año) × cuota del cantón en la
     superficie de cultivo (ESA WorldCover cultivos + árboles, < 900 m); rendimiento = tendencia
     provincial (t por ha sembrada).

Todo cantón es `evidence = indice_subnacional_no_validado` (no hay producción por cantón para validar).
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from .config import ARTIFACTS, DATA_PROCESSED, ROOT
from .dataset import load_price_features
from .features import BiasCorrection, build_features
from .inference import register_area
from .model import ID_COLS, NON_CLIMATE, risk_class
from .predict import VERSION, exposure, latest_price, load_bundle
from .etl.cantons import norm

CANTONS = ROOT / "data" / "cantons_supabase.csv"
PROVINCES = ROOT / "data" / "provinces_supabase.csv"
OUT = ARTIFACTS / f"loss_predictions_areas_{VERSION}"


def warming_offset() -> dict[int, float]:
    """ERA5 nacional: media 1991–2020 − media 1961–1990, por mes (°C)."""
    d = pd.read_parquet(DATA_PROCESSED / "climate_daily.parquet", columns=["date", "area_name", "t2m_c"])
    d = d[d.area_name == "national"].assign(y=lambda x: x.date.dt.year, m=lambda x: x.date.dt.month)
    a = d[d.y.between(1991, 2020)].groupby("m").t2m_c.mean()
    b = d[d.y.between(1961, 1990)].groupby("m").t2m_c.mean()
    return (a - b).to_dict()


def canton_bias(daily: pd.DataFrame, meta: pd.DataFrame) -> BiasCorrection:
    warm = warming_offset()
    ref = daily[daily.date.dt.year.between(1991, 2020)].assign(m=lambda x: x.date.dt.month)
    era = ref.groupby(["area_name", "m"])[["t2m_c", "t2m_min_c", "t2m_max_c"]].mean()
    deltas = {}
    for r in meta.itertuples():
        wc = r.worldclim
        dd = {"t2m_c": {}, "t2m_min_c": {}, "t2m_max_c": {}}
        for m in range(1, 13):
            w = wc.get(m) or wc.get(str(m)) or {}
            for var, key in (("t2m_c", "tavg"), ("t2m_min_c", "tmin"), ("t2m_max_c", "tmax")):
                e = era.loc[(r.area_name, m), var] if (r.area_name, m) in era.index else np.nan
                v = (w.get(key) * 0.1 - e + warm[m]) if w.get(key) is not None and not np.isnan(e) else 0.0
                dd[var][m] = float(v)
        deltas[r.area_name] = dd
    area_meta = meta[["area_name", "lat", "elev_m"]].assign(elev_m=lambda x: x.elev_m.fillna(100.0))
    wc_dummy = pd.DataFrame(columns=["area_name", "month", "wc_tavg_c", "wc_tmin_c", "wc_tmax_c"])
    return BiasCorrection.fit(daily, wc_dummy, area_meta, temp_delta=deltas)


def canton_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(DATA_PROCESSED / "climate_daily_cantons.parquet")
    meta = pd.read_pickle(DATA_PROCESSED / "canton_meta.pkl")
    meta = meta[meta.area_name.isin(daily.area_name.unique())]
    bc = canton_bias(daily, meta)
    feats = build_features(daily, bc).merge(load_price_features(), on="year", how="left")
    enso = pd.read_parquet(DATA_PROCESSED / "enso_yearly.parquet")[["year", "nino12_jan_jun", "oni_jan_jun"]]
    return feats.merge(enso, on="year", how="left"), meta


def predict_area(bundle, X: pd.DataFrame) -> dict:
    m = bundle["model"]
    out = m.predict(X)
    contrib = m.model.contributions(X.reset_index(drop=True)).mean()
    mean_x = X[m.features].mean().fillna(0.0)
    factors = sorted(({"feature": k, "value": round(float(mean_x[k]), 2), "contribution_pct": round(float(-v), 2)}
                      for k, v in contrib.items() if k not in NON_CLIMATE),
                     key=lambda d: -abs(d["contribution_pct"]))[:5]
    loss = float(out.loss_pct.mean())
    return {"loss_pct": round(loss, 2), "loss_pct_low": round(float(out.loss_p10.mean()), 2),
            "loss_pct_high": round(float(out.loss_p90.mean()), 2), "risk_class": risk_class(loss),
            "prob_loss_gt20": round(float(out.prob_loss_gt20.mean()), 3) if "prob_loss_gt20" in out else None,
            "top_factors": factors, "extrapolated": bool(out.extrapolated.any()),
            "evidence": out.evidence.iloc[0], "scenario_years": [int(y) for y in X.year]}


def run(verbose: bool = True) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    bundle = load_bundle()
    m = bundle["model"]
    feats, meta = canton_features()
    cant = pd.read_csv(CANTONS, dtype=str)
    prov_ids = pd.read_csv(PROVINCES, dtype=str)
    # exposición provincial (ha sembradas y rendimiento de tendencia) → reparto por superficie de cultivo
    panel = pd.read_parquet(DATA_PROCESSED / "training_panel.parquet")
    prod = pd.read_parquet(DATA_PROCESSED / "production.parquet")
    prod = prod[(prod.level == "province") & prod.planted_ha.notna()].sort_values("year")
    last = prod.groupby("area_name").tail(1)
    planted = {norm(r.area_name): float(r.planted_ha) for r in last.itertuples()}
    exp = exposure(panel)                                  # provincias de entrenamiento (tendencia propia)
    yld_prov = {norm(k): float(v) for k, v in exp.expected_yield_t_ha.items() if k != "national"}
    yld_default = float(np.median(list(yld_prov.values())))
    meta = meta.assign(pkey=meta.province.map(norm))
    share = meta.crop_ha / meta.groupby("pkey").crop_ha.transform("sum")
    meta = meta.assign(share=share.fillna(0.0))
    price, price_year = latest_price()

    rows = []
    for r in meta.itertuples():
        hist = feats[feats.area_name == r.area_name].drop(columns="area_name")
        try:
            register_area(bundle, r.area_name, hist)
        except ValueError:
            continue
        for sc, years in bundle["scenario_years"].items():
            X = feats[(feats.area_name == r.area_name) & feats.year.isin(years)]
            X = X.dropna(subset=[c for c in m.features if c not in m.model.spec.fill_zero])
            if X.empty:
                continue
            X = X.assign(**{c: np.nan for c in NON_CLIMATE if c in X})[ID_COLS + m.features]
            res = predict_area(bundle, X)
            ha = planted.get(r.pkey, np.nan) * r.share
            yld = yld_prov.get(r.pkey, yld_default)
            loss_t = ha * yld * res["loss_pct"] / 100 if np.isfinite(ha) else None
            rows.append({"area_id": r.area_name, "kind": "canton", "name": r.name, "province": r.province,
                         "scenario_id": sc, **res, "exposed_ha": round(ha, 1) if np.isfinite(ha) else None,
                         "expected_yield_t_ha": round(yld, 3),
                         "loss_t": round(loss_t, 1) if loss_t is not None else None,
                         "price_usd_t": price, "loss_usd": round(loss_t * price) if loss_t is not None else None,
                         "mask_fallback": bool(r.mask_fallback), "model_version": bundle["version"]})
    out = pd.DataFrame(rows)

    # provincias y país (de ml.predict) con su id de Supabase
    pp = pd.read_parquet(ARTIFACTS / f"loss_predictions_{VERSION}.parquet")
    pp = pp.merge(prov_ids.dropna(subset=["model_name"]), left_on="area_name", right_on="model_name")
    pp = pp.assign(area_id=pp.id, kind=pp.kind, province=np.where(pp.kind == "province", pp.name, None))
    pp["top_factors"] = pp.top_factors.map(json.loads)
    pp["scenario_years"] = pp.scenario_years.map(json.loads)
    cols = [c for c in out.columns if c in pp.columns]
    allp = pd.concat([pp[cols], out[cols]], ignore_index=True)

    # bundle con los cantones registrados (normal climática + vectores de escenario por uuid)
    joblib_path = ARTIFACTS / f"cacao_loss_{VERSION}.joblib"
    import joblib
    for cid in out.area_id.unique():
        X = feats[feats.area_name == cid]
        sens = bundle["sensitivities"].get(cid, bundle["sensitivities"]["national"])
        bundle["scenario_features"][cid] = {
            sc: {**X[X.year.isin(yrs)][m.features + ["nino12_jan_jun", "oni_jan_jun"]].mean().round(4).dropna()
                 .drop(list(NON_CLIMATE), errors="ignore").to_dict(), "_area": cid, "_sens": sens}
            for sc, yrs in bundle["scenario_years"].items() if X.year.isin(yrs).any()}
    from .inference import attach_area_ids
    attach_area_ids(bundle, dict(zip(pp.area_id, pp.area_name)))
    joblib.dump(bundle, joblib_path)

    save = allp.assign(top_factors=allp.top_factors.map(json.dumps),
                       scenario_years=allp.scenario_years.map(json.dumps))
    save.to_parquet(f"{OUT}.parquet", index=False)
    save.to_csv(f"{OUT}.csv", index=False)
    if verbose:
        c = out[out.scenario_id == "nino_extremo"].sort_values("loss_pct", ascending=False)
        print(f"cantones con predicción: {out.area_id.nunique()} / {len(cant)}")
        print("Niño extremo, top 10 cantones:")
        print(c[["name", "province", "loss_pct", "prob_loss_gt20", "exposed_ha", "loss_t"]].head(10).to_string(index=False))
        print("\nPérdida media por provincia (cantones) y escenario:")
        print(out.pivot_table(index="province", columns="scenario_id", values="loss_pct", aggfunc="mean").round(1).to_string())
        print(f"\nGuardado: {OUT}.csv/.parquet y bundle con {len(bundle['scenario_features'])} áreas")
    return allp


if __name__ == "__main__":
    run()
