"""Modelo de pérdida DENTRO del backend (what-if en vivo).

ML entrega un bundle .joblib (ver docs/backend/03-integracion-ml.md) y, opcionalmente,
`ml/inference.py` (paquete `ml/` de la raíz del repo, rama de Arthur) con `adjust_features(...)`
y `predict(...)`. Si existe ese módulo, el backend usa su lógica; si no, usa la genérica de aquí.

Las features del modelo de ML son ANOMALÍAS dentro de cada área (x − media del área): el
bundle debe traer `area_means` para que el backend las reste antes de predecir.

⚠ joblib/pickle ejecuta código al cargar: solo cargar archivos del equipo.
"""
import importlib
import logging
import sys
import threading
from typing import Any

from ..core.config import REPO_DIR, get_settings
from ..core.errors import bad_request, unavailable
from ..data import get_source
from . import climate, enso, labels, losses
from .territory import get_area

log = logging.getLogger(__name__)
_lock = threading.Lock()
_state: dict[str, Any] = {"bundle": None, "error": None, "inference": None, "path": None}

LIMITS = {"temp_delta_c": (-3.0, 4.0), "rain_delta_pct": (-50.0, 100.0), "nino12_anom": (-3.0, 6.0), "oni": (-3.0, 3.5)}


def load() -> dict:
    """Carga (o recarga) el bundle. No lanza: deja el error en el estado para /health."""
    s = get_settings()
    with _lock:
        _state.update(bundle=None, error=None, inference=None, path=str(s.model_file))
        if s.predictor_mode == "off":
            _state["error"] = "PREDICTOR_MODE=off"
            return status()
        if not s.model_file.exists():
            _state["error"] = f"No existe {s.model_file} (ML debe copiar ahí el .joblib)"
            return status()
        # Primero el path: el .joblib guarda objetos de ml/ (CacaoLossModel) y al cargarlo hay que poder importarlos
        if str(REPO_DIR) not in sys.path:
            sys.path.append(str(REPO_DIR))   # para importar ml/ de la raíz del repo
        try:
            import joblib
            b = joblib.load(s.model_file)
            if not isinstance(b, dict) or "model" not in b or "features" not in b:
                raise ValueError("El .joblib debe ser un dict con al menos 'model' y 'features'")
            _state["bundle"] = b
        except Exception as e:  # noqa: BLE001 — se reporta en /health
            _state["error"] = f"No se pudo cargar el modelo: {e}"
            log.exception("Error cargando el modelo")
        try:
            _state["inference"] = importlib.import_module(s.ml_inference_module)
        except ModuleNotFoundError:
            _state["inference"] = None
    return status()


def status() -> dict:
    b = _state["bundle"]
    return {"loaded": b is not None, "version": (b or {}).get("version"), "path": _state["path"],
            "error": _state["error"], "custom_inference": _state["inference"] is not None,
            "features": (b or {}).get("features")}


# ── features base de un área × escenario ──────────────────────────────
def base_features(area: dict, crop: str, scenario: str) -> dict[str, float]:
    b = _state["bundle"] or {}
    sf = (b.get("scenario_features") or {}).get(area["id"], {}).get(scenario)
    if sf:
        return dict(sf)
    window = climate.risk_window(crop, area.get("region"))
    risk = climate.risk_table(area["id"], scenario, window)
    clim = climate.climate_summary(area["id"], scenario, ["precip", "heavy_rain_days", "saturated_days", "rh_mean"])

    def window_sum(v):
        months = (clim.get(v) or {}).get("months") or []
        vals = [m["mean"] for m in months if m["month"] in window and m["mean"] is not None]
        return sum(vals) if vals else None

    fav = risk["favorable_days_window"]
    rwm = risk["risk_window_mean"]
    oni, n12 = _enso_for(scenario)
    suit = next(iter(get_source().suitability(area["id"], crop, ["normal"])), None)
    annual_p = (clim.get("precip") or {}).get("annual")
    def window_mean(v):
        months = (clim.get(v) or {}).get("months") or []
        vals = [m["mean"] for m in months if m["month"] in window and m["mean"] is not None]
        return sum(vals) / len(vals) if vals else None

    feats = {
        "fav_days_monilia": fav.get("monilia"), "fav_days_phytophthora": fav.get("phytophthora"),
        "fav_days_escoba": fav.get("escoba_bruja"),
        "heavy_rain_days": window_sum("heavy_rain_days"), "saturated_days": window_sum("saturated_days"),
        "precip_total_mm": window_sum("precip"),
        "risk_index_mean": (sum(rwm.values()) / len(rwm)) if rwm else None,
        "oni_jan_jun": oni, "nino12_anom_jan_jun": n12,
        "suitability_now": float(suit["score"]) if suit else None,
        "rain_total_vs_opt": max(0.0, annual_p - 3000) if annual_p is not None else None,
        "yield_anom_prev": 0.0,
        "rh_mean": window_mean("rh_mean"),
    }
    for alias, name in ALIASES.items():   # nombres del paquete ml/ (rama de Arthur)
        feats.setdefault(alias, feats.get(name))
    return {k: float(v) for k, v in feats.items() if v is not None}


# nombre en ml/ (Arthur)  →  nombre en la BD / backend
ALIASES = {"nino12_jan_jun": "nino12_anom_jan_jun", "suitability": "suitability_now", "rain_total": "precip_total_mm",
           "rain_excess_opt": "rain_total_vs_opt", "y_anom_prev": "yield_anom_prev"}


def _enso_for(scenario: str) -> tuple[float | None, float | None]:
    if scenario == "actual":
        cur = enso.current()
        return ((cur.get("oni") or {}).get("value"), (cur.get("nino12_anom") or {}).get("value"))
    cls = {"nino": "nino", "nina": "nina"}.get(scenario, "neutral")
    years = [y for y in enso.years() if y.get("enso_class") == cls]
    if not years:
        return None, None
    avg = lambda k: sum(float(y[k]) for y in years if y.get(k) is not None) / max(1, sum(1 for y in years if y.get(k) is not None))
    return round(avg("oni_jan_jun"), 2), round(avg("nino12_anom_jan_jun"), 2)


def adjust(features: dict[str, float], adj: dict[str, float], area_ctx: dict) -> dict[str, float]:
    inf = _state["inference"]
    if inf is not None and hasattr(inf, "adjust_features"):
        return inf.adjust_features(dict(features), adj, area_ctx)
    f = dict(features)
    r = adj.get("rain_delta_pct", 0) / 100
    t = adj.get("temp_delta_c", 0)
    for k, mult in (("heavy_rain_days", 1 + r), ("saturated_days", 1 + r), ("precip_total_mm", 1 + r),
                    ("rain_total", 1 + r), ("rain_max_1d", 1 + r), ("rain_max_5d", 1 + r),
                    ("fav_days_phytophthora", (1 + 0.5 * r) * (1 - 0.02 * t)),
                    ("fav_days_monilia", (1 + 0.2 * r) * (1 - 0.05 * t)),
                    ("fav_days_escoba", (1 + 0.2 * r) * (1 - 0.03 * t))):
        if k in f:
            f[k] = max(0.0, f[k] * mult)
    for k in ("rain_total_vs_opt", "rain_excess_opt"):
        if k in f and area_ctx.get("annual_precip") is not None:
            f[k] = max(0.0, area_ctx["annual_precip"] * (1 + r) - 3000)
    for k in ("t_mean", "tmax_mean", "tmin_mean"):
        if k in f:
            f[k] += t
    if adj.get("oni") is not None:
        f["oni_jan_jun"] = adj["oni"]
    if adj.get("nino12_anom") is not None:
        f["nino12_anom_jan_jun"] = f["nino12_jan_jun"] = adj["nino12_anom"]
    return f


def _generic_predict(b: dict, feats: dict[str, float], area: dict | None = None) -> dict:
    import pandas as pd
    names = b["features"]
    am = b.get("area_means") or {}
    area_mean = (am.get(area["id"]) or am.get(area["name"]) or {}) if area else {}
    means = {n: 0.0 for n in names} if area_mean else (b.get("feature_means") or {})
    # anomalía dentro del área si el bundle trae medias por área; si no, valor absoluto
    row = {n: (feats[n] - area_mean.get(n, 0.0)) if n in feats else means.get(n, 0.0) for n in names}
    X = pd.DataFrame([row], columns=names)

    def loss_of(model, x):
        return max(0.0, min(100.0, -float(model.predict(x)[0])))   # anomalía negativa = pérdida

    pct = loss_of(b["model"], X)
    low = loss_of(b["high"], X) if b.get("high") is not None else None   # cuantil alto de anomalía = pérdida baja
    high = loss_of(b["low"], X) if b.get("low") is not None else None
    contribs = []
    for n in names:
        if n in means:
            x2 = X.copy()
            x2[n] = means[n]
            contribs.append({"feature": n, "value": row[n], "contribution_pct": round(pct - loss_of(b["model"], x2), 2)})
    contribs.sort(key=lambda c: -abs(c["contribution_pct"]))
    rng = b.get("feature_ranges") or {}
    oor = any(n in rng and not (rng[n][0] <= row[n] <= rng[n][1]) for n in names)
    return {"loss_pct": pct, "loss_pct_low": low, "loss_pct_high": high, "top_factors": contribs[:5], "out_of_range": oor}


def _synthetic_predict(base_pct: float, adj: dict) -> dict:
    """Solo DATA_SOURCE=mock sin modelo: respuesta sintética con el mismo formato."""
    r, t = adj.get("rain_delta_pct", 0) / 100, adj.get("temp_delta_c", 0)
    n12 = adj.get("nino12_anom")
    pct = base_pct * (1 + 0.6 * r) * (1 + 0.04 * t) * (1 + 0.06 * (n12 or 0))
    pct = max(0.0, min(100.0, pct))
    return {"loss_pct": pct, "loss_pct_low": pct * 0.55, "loss_pct_high": min(100, pct * 1.55),
            "top_factors": [{"feature": "heavy_rain_days", "value": None, "contribution_pct": round(pct * 0.3, 1)}],
            "out_of_range": abs(r) > 0.6 or abs(t) > 3}


def what_if(area_id: str, crop: str, base_scenario: str, adj: dict[str, float | None]) -> dict:
    for k, v in adj.items():
        if v is not None and k in LIMITS and not LIMITS[k][0] <= v <= LIMITS[k][1]:
            raise bad_request("adjust_out_of_limits", f"{k}={v} fuera de {LIMITS[k]}")
    adj = {k: v for k, v in adj.items() if v is not None}
    area = get_area(area_id)
    base = losses.loss_for(area_id, crop, base_scenario)
    b = _state["bundle"]
    synthetic = False
    if b is None:
        if get_source().name != "mock":
            raise unavailable("model_not_loaded", status()["error"] or "Modelo no cargado")
        feats0, feats = {}, {}
        res = _synthetic_predict(base["loss_pct"] or 0, adj)
        synthetic = True
    else:
        feats0 = base_features(area, crop, base_scenario)
        ctx = {"annual_precip": (climate.climate_summary(area_id, base_scenario, ["precip"]).get("precip") or {}).get("annual")}
        feats = adjust(feats0, adj, ctx)
        inf = _state["inference"]
        res = (inf.predict(b, feats) if inf is not None and hasattr(inf, "predict")
               else _generic_predict(b, feats, area))

    pct = round(float(res["loss_pct"]), 1)
    ha, yld, price = base["exposed_ha"] or 0, base.get("expected_yield_t_ha"), base.get("price_usd_t")
    if yld is None and base.get("loss_t") and base.get("loss_pct"):
        yld = base["loss_t"] / (ha * base["loss_pct"] / 100) if ha else None
    if price is None and base.get("loss_t"):
        price = (base["loss_usd"] or 0) / base["loss_t"]
    loss_t = round(ha * (yld or 0) * pct / 100)
    out = {
        "area_id": area_id, "area_name": area["name"], "crop": crop, "base_scenario": base_scenario, "adjust": adj,
        "features_base": feats0, "features_used": feats,
        "loss_pct": pct, "loss_pct_low": _r(res.get("loss_pct_low")), "loss_pct_high": _r(res.get("loss_pct_high")),
        "loss_t": loss_t, "loss_usd": round(loss_t * (price or 0)), "risk_class": labels.risk_class(pct),
        "base_loss_pct": base["loss_pct"], "delta_vs_base_pct": round(pct - (base["loss_pct"] or 0), 1),
        "top_factors": [{**f, "label": labels.feature_label(f["feature"])} for f in res.get("top_factors", [])],
        "model": {"name": "sintetico (sin modelo)" if synthetic else (b or {}).get("version")},
        "synthetic": synthetic,
        "disclaimer": labels.DISCLAIMER,
    }
    if res.get("out_of_range"):
        out["warning"] = "Combinación fuera del rango de entrenamiento: interpretar con cautela."
    return out


def _r(v):
    return None if v is None else round(float(v), 1)
