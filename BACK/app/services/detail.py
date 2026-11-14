"""Panel de un cantón en una sola respuesta (junta 7+ tablas)."""
from ..core.cache import cached
from ..core.config import get_settings
from ..data import get_source
from . import climate, labels, losses
from .territory import get_area

CORE_VARS = ["t2m", "precip", "rh_mean", "heavy_rain_days", "saturated_days"]


@cached(ttl=get_settings().cache_ttl_seconds)
def build(area_id: str, crop: str, scenario: str) -> dict:
    src = get_source()
    area = get_area(area_id)
    loss = losses.loss_for(area_id, crop, scenario, required=False)
    normal = losses.loss_for(area_id, crop, "normal", required=False) if scenario != "normal" else None
    window = climate.risk_window(crop, area.get("region"))
    risk = climate.risk_table(area_id, scenario, window)
    clim = climate.climate_summary(area_id, scenario, CORE_VARS)
    static = src.static_features(area_id)
    suit = next(iter(src.suitability(area_id, crop, [scenario])), None)
    exposure = next(iter(src.exposure(crop, area_id)), None)

    loss_block = None
    if loss:
        loss_block = {k: loss.get(k) for k in losses.LOSS_FIELDS}
        if normal:
            loss_block["vs_normal"] = {
                "loss_pct": normal["loss_pct"],
                "delta_pct": round((loss["loss_pct"] or 0) - (normal["loss_pct"] or 0), 1),
                "delta_usd": round((loss["loss_usd"] or 0) - (normal["loss_usd"] or 0)),
            }

    gaps = []
    if not loss:
        gaps.append("Todavía no hay predicción del modelo para este cantón y escenario.")
    if not risk["months"]:
        gaps.append("Falta el índice de riesgo de enfermedad para este escenario.")
    if any(not t.get("validated") for p in src.pathogens(crop) for t in p.get("disease_thresholds", [])):
        gaps.append("Umbrales de enfermedad referenciales, no validados en campo.")
    if exposure and exposure.get("method") != "espac_direct":
        gaps.append("Superficie de cacao del cantón estimada (no medida directamente por ESPAC).")

    return {
        "area": {"id": area["id"], "name": area["name"], "kind": area["kind"],
                 "province": (area.get("province") or {}).get("name"), "region": area.get("region"),
                 "crop_ha": float(exposure["crop_ha"]) if exposure else None},
        "crop": crop, "scenario": scenario,
        "loss": loss_block,
        "top_factors": losses.factors(loss) if loss else [],
        "monthly_risk": risk["months"], "dominant_pathogen": risk["dominant_pathogen"],
        "risk_window_months": window, "peak_risk": risk["peak"],
        "favorable_days_window": risk["favorable_days_window"],
        "climate": {v: {"annual": d["annual"], "unit": d["unit"]} for v, d in clim.items()},
        "requirement_check": climate.requirement_check(crop, clim, static),
        "suitability": ({"score": float(suit["score"]), "class": suit["class"],
                         "limiting_factors": suit.get("limiting_factors") or []} if suit else None),
        "static": static,
        "model": losses.model_info(crop),
        "data_gaps": gaps,
        "disclaimer": labels.DISCLAIMER,
        "data_source": src.name,
    }
