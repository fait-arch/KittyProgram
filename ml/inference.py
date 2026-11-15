"""Interfaz del modelo para el backend (contrato de docs/backend/03-integracion-ml.md).

El backend (rama emilio/backend, `BACK/app/services/predictor.py`) carga el bundle con
`joblib.load` e importa este módulo (`ML_INFERENCE_MODULE=ml.inference`). Solo usa:

    adjust_features(features, adjust, area_ctx) -> features     # sliders del what-if
    predict(bundle, features) -> {"loss_pct", "loss_pct_low", "loss_pct_high",
                                  "top_factors", "out_of_range", ...}

Bundle (`ml/artifacts/cacao_loss_v1.joblib`, un dict):

    version, features, model (CacaoLossModel), feature_ranges, feature_means, explain,
    sklearn_version, scenario_features {área: {escenario: {feature: valor, "_area": área}}},
    sensitivities {área: {...}}, scenario_years, metrics

Las áreas se identifican por NOMBRE ("national", "Los Rios", …). Si el backend usa uuid,
`attach_area_ids(bundle, {uuid: nombre})` copia todo bajo el uuid. Para un cantón nuevo,
`register_area(bundle, id, historial)` le calcula su normal climática y sus sensibilidades.

Importante: el vector de features lleva la clave "_area" (el área cuya normal climática se
usa; si no está, "_province" y si tampoco, la nacional) y "_sens" (sus sensibilidades para los
sliders). Los vectores de `scenario_features` ya las traen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import CacaoLossModel
from .scenarios import CONTEXT, MAX_DAYS, fit_sensitivities

NATIONAL = "national"
SLIDERS = {"rain_delta_pct", "temp_delta_c", "nino12_anom", "oni"}


# ── Construcción del bundle ──────────────────────────────────────────────────────────
def build_bundle(model: CacaoLossModel, train: pd.DataFrame, climate: pd.DataFrame,
                 scenario_features: dict, scenario_years: dict, metrics: dict) -> dict:
    import sklearn
    feats = model.features
    sens = fit_sensitivities(climate)
    for area, scs in scenario_features.items():
        for v in scs.values():
            v["_sens"] = sens.get(area, sens.get(NATIONAL))
    return {
        "version": f"cacao_loss_{model.version}",
        "features": feats,
        "model": model,
        "feature_ranges": {f: [float(train[f].min()), float(train[f].max())] for f in feats},
        "feature_means": {f: float(train[f].mean()) for f in feats},
        "explain": "linear",
        "sklearn_version": sklearn.__version__,
        "scenario_features": scenario_features,
        "scenario_years": scenario_years,
        "sensitivities": sens,
        "metrics": metrics,
    }


def area_key(bundle: dict, features: dict) -> str:
    known = set(bundle["model"].model.pre_.mean_.index)
    for k in ("_area", "_province"):
        if features.get(k) in known:
            return features[k]
    return NATIONAL


def attach_area_ids(bundle: dict, ids: dict[str, str]) -> dict:
    """Duplica normal, escala de ruido, sensibilidades y escenarios de cada nombre bajo su id."""
    m = bundle["model"]
    pre = m.model.pre_
    for area_id, name in ids.items():
        if name not in pre.mean_.index:
            continue
        pre.mean_.loc[area_id], pre.sd_.loc[area_id] = pre.mean_.loc[name], pre.sd_.loc[name]
        if name in m.noise_scale:
            m.noise_scale[area_id] = m.noise_scale[name]
        for key in ("sensitivities", "scenario_features"):
            if name in bundle[key]:
                bundle[key][area_id] = bundle[key][name]
    return bundle


def register_area(bundle: dict, area_id: str, history: pd.DataFrame) -> None:
    """Cantón / polígono nuevo. `history`: features ene–jun por año (≥ 10 años de 1991–2020)
    con columnas year + las del modelo (+ nino12_jan_jun y oni_jan_jun para las sensibilidades)."""
    bundle["model"].model.pre_.add_area(area_id, history)
    h = history.assign(area_name=area_id)
    if set(CONTEXT) <= set(h.columns) and "t_mean" in h.columns:
        bundle["sensitivities"].update(fit_sensitivities(h))
    sens = bundle["sensitivities"].get(area_id, bundle["sensitivities"][NATIONAL])
    cols = list(dict.fromkeys(bundle["features"] + [c for c in CONTEXT if c in history.columns]))
    bundle["scenario_features"][area_id] = {
        "normal": {**history[cols].mean().round(4).to_dict(), "_area": area_id, "_sens": sens}}


# ── Sliders ──────────────────────────────────────────────────────────────────────────
def adjust_features(features: dict, adjust: dict, area_ctx: dict | None = None,
                    sensitivities: dict | None = None) -> dict:
    """Aplica los sliders al vector base, propagando la lluvia a las variables que dependen
    de ella con las pendientes históricas del área (ver ml/scenarios.py).

    adjust: nino12_anom / oni (°C, reemplazan el ENSO del vector → cambian la lluvia esperada),
            rain_delta_pct (% sobre la lluvia resultante), temp_delta_c (°C).
    """
    f = dict(features)
    sens = sensitivities or {}
    s = (f.get("_sens") or sens.get(f.get("_area")) or sens.get(f.get("_province"))
         or sens.get(NATIONAL) or {})
    rain0 = float(f.get("rain_total", 0.0))
    d_rain = 0.0
    if adjust.get("nino12_anom") is not None:
        d_rain += s.get("mm_per_nino12", 0.0) * (adjust["nino12_anom"] - f.get("nino12_jan_jun", 0.0))
        f["nino12_jan_jun"] = float(adjust["nino12_anom"])
    elif adjust.get("oni") is not None:
        d_rain += s.get("mm_per_oni", 0.0) * (adjust["oni"] - f.get("oni_jan_jun", 0.0))
    if adjust.get("oni") is not None:
        f["oni_jan_jun"] = float(adjust["oni"])
    rain1 = max(0.0, rain0 + d_rain) * (1 + adjust.get("rain_delta_pct", 0.0) / 100)
    d_rain = rain1 - rain0
    d_t = adjust.get("temp_delta_c", 0.0) or 0.0
    if "rain_total" in f:
        f["rain_total"] = rain1
    if "saturated_days" in f:
        f["saturated_days"] = float(np.clip(f["saturated_days"] + s.get("sat_per_mm", 0) * d_rain, 0, MAX_DAYS))
    if "fav_days_phytophthora" in f:
        f["fav_days_phytophthora"] = float(np.clip(
            f["fav_days_phytophthora"] + s.get("fav_per_mm", 0) * d_rain + s.get("fav_per_c", 0) * d_t,
            0, MAX_DAYS))
    if "solar_mean" in f:
        f["solar_mean"] = max(0.0, f["solar_mean"] + s.get("sol_per_mm", 0) * d_rain)
    return f


# ── Predicción ───────────────────────────────────────────────────────────────────────
def predict(bundle: dict, features: dict) -> dict:
    """Un vector de features → pérdida (%) con intervalo y factores (formato del backend)."""
    m: CacaoLossModel = bundle["model"]
    optional = set(m.model.spec.fill_zero)                # p. ej. EVI: sin dato = verdor normal
    missing = [c for c in m.features if c not in features and c not in optional]
    if missing:
        raise ValueError(f"Faltan features: {missing}")
    area = area_key(bundle, features)

    def val(c):
        v = features.get(c)
        return np.nan if v is None else float(v)
    X = pd.DataFrame([{"area_name": area, "year": 0, **{c: val(c) for c in m.features}}])
    r = m.predict(X).iloc[0]
    c = m.model.contributions(X).iloc[0]
    factors = sorted(({"feature": k, "value": None if np.isnan(val(k)) else round(val(k), 2),
                       "contribution_pct": round(float(-v), 2)} for k, v in c.items()),
                     key=lambda d: -abs(d["contribution_pct"]))
    return {
        "loss_pct": float(r.loss_pct), "loss_pct_low": float(r.loss_p10),
        "loss_pct_high": float(r.loss_p90), "top_factors": factors[:5],
        "out_of_range": bool(r.extrapolated),
        "prob_loss_gt20": float(r.prob_loss_gt20) if "prob_loss_gt20" in r else None,
        "y_anom_pct": float(r.y_anom_pct), "risk_class": r.risk_class, "evidence": r.evidence,
        "area_used": area, "model_version": bundle["version"],
    }
