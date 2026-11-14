"""Pérdidas: mapa, resumen, comparación de escenarios y zonas (Fase 2)."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..core.errors import bad_request
from ..data import get_source
from ..services import climate, detail, losses, territory

router = APIRouter(tags=["pérdidas"])
KIND = Query("canton", pattern="^(province|canton)$")


def _prov_name(province: str | None) -> str | None:
    p = territory.resolve_province(province)
    return p["name"] if p else None


@router.get("/losses", summary="Pérdida estimada por área (colorea el mapa)")
def list_losses(scenario: str = "nino", kind: str = KIND, province: str | None = None, crop: str = "cacao"):
    climate.check_scenario(scenario)
    return losses.list_losses(crop, scenario, kind, _prov_name(province))


@router.get("/losses/geojson", summary="GeoJSON con la pérdida en las propiedades (mapa en una sola llamada)")
def losses_geojson(scenario: str = "nino", kind: str = KIND, province: str | None = None, crop: str = "cacao"):
    climate.check_scenario(scenario)
    prov = territory.resolve_province(province)
    data = losses.list_losses(crop, scenario, kind, prov["name"] if prov else None)
    extra = {i["area_id"]: {k: i[k] for k in ("loss_pct", "loss_pct_low", "loss_pct_high", "loss_t", "loss_usd",
                                               "exposed_ha", "risk_class")} for i in data["items"]}
    fc = territory.feature_collection(kind, prov["id"] if prov else None, extra=extra)
    fc["scenario"], fc["model"], fc["classes"] = scenario, data["model"], data["classes"]
    return JSONResponse(fc, media_type="application/geo+json")


@router.get("/losses/summary", summary="Totales del escenario (país o provincia)")
def losses_summary(scenario: str = "nino", province: str | None = None, crop: str = "cacao",
                   vs: str | None = Query("normal", description="Escenario de comparación; vacío para omitir")):
    climate.check_scenario(scenario)
    if vs:
        climate.check_scenario(vs)
    return losses.summary(crop, scenario, _prov_name(province), vs or None)


@router.get("/compare", summary="Mismo cantón en varios escenarios (Fase 2)")
def compare(area_id: str, scenarios: str = "normal,nino,ssp245_2050", crop: str = "cacao"):
    sc = [s.strip() for s in scenarios.split(",") if s.strip()]
    if not 1 <= len(sc) <= 6:
        raise bad_request("invalid_scenarios", "Entre 1 y 6 escenarios")
    items = []
    for s in sc:
        climate.check_scenario(s)
        d = detail.build(area_id, crop, s)
        items.append({"scenario": s, "loss": d["loss"], "suitability": d["suitability"],
                      "dominant_pathogen": d["dominant_pathogen"], "climate": d["climate"],
                      "requirement_check": d["requirement_check"]})
    return {"area_id": area_id, "crop": crop, "items": items}


@router.get("/zones", summary="Matriz segura / manejo / transición / crítica (Fase 2)")
def zones(future: str = Query("ssp245_2050", pattern="^ssp(245|585)_2050$"), crop: str = "cacao",
          province: str | None = None):
    prov = territory.resolve_province(province)
    out = []
    for z in get_source().zones(crop, future):
        a = z.get("areas") or {}
        if prov and a.get("parent_id") != prov["id"]:
            continue
        out.append({"area_id": z["area_id"], "name": a.get("name"), "zone_class": z["zone_class"],
                    "suitability_now": z.get("suitability_now"), "suitability_future": z.get("suitability_future"),
                    "nino_risk": z.get("nino_risk")})
    return {"future": future, "legend": {"segura": "Apta y riesgo bajo", "manejo": "Apta, pero riesgo Niño alto",
                                         "transicion": "Pierde aptitud climática", "critica": "Pierde aptitud y riesgo alto"},
            "items": out}
