"""Territorio y datos por área: lista, GeoJSON, búsqueda por punto, clima, riesgo, aptitud, detalle."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..core.errors import not_found
from ..data import get_source
from ..services import climate, detail, territory

router = APIRouter(prefix="/areas", tags=["áreas"])
KIND = Query("canton", pattern="^(province|canton)$")


def _ym(v: str | None, end: bool = False) -> str | None:
    if not v:
        return None
    return f"{v}-01" if len(v) == 7 else v if len(v) == 10 else (f"{v}-12-01" if end else f"{v}-01-01")


@router.get("", summary="Áreas sin geometría")
def list_areas(kind: str = KIND, province: str | None = None, has_crop: str | None = None):
    prov = territory.resolve_province(province)
    rows = get_source().areas(kind=kind, parent_id=prov["id"] if prov else None)
    provs = territory.province_index()
    exp = {e["area_id"]: float(e["crop_ha"]) for e in get_source().exposure(has_crop)} if has_crop else {}
    out = []
    for a in rows:
        if has_crop and a["id"] not in exp:
            continue
        p = provs.get(a.get("parent_id") or "")
        out.append({"id": a["id"], "name": a["name"], "kind": a["kind"], "region": a.get("region"),
                    "province": {"id": p["id"], "name": p["name"]} if p else None,
                    "area_ha": float(a["area_ha"]) if a.get("area_ha") is not None else None,
                    "crop_ha": exp.get(a["id"])})
    return out


@router.get("/geojson", summary="FeatureCollection para el mapa (geometría simplificada)")
def geojson(kind: str = KIND, province: str | None = None):
    prov = territory.resolve_province(province)
    fc = territory.feature_collection(kind, prov["id"] if prov else None)
    return JSONResponse(fc, media_type="application/geo+json", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/lookup", summary="¿En qué cantón cae este punto?")
def lookup(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    hit = territory.lookup(lat, lon)
    if not hit:
        raise not_found("point_outside_areas", "El punto no cae en ningún cantón cargado")
    return hit


@router.get("/{area_id}")
def get_area(area_id: str, crop: str = "cacao"):
    a = territory.get_area(area_id)
    src = get_source()
    return {**{k: a.get(k) for k in ("id", "name", "kind", "region", "inec_dpa_code", "province", "area_ha")},
            "centroid": territory.centroid(area_id), "static": src.static_features(area_id),
            "exposure": src.exposure(crop, area_id)}


@router.get("/{area_id}/climate", summary="Climatología mensual del escenario")
def area_climate(area_id: str, scenario: str = "normal", variables: str | None = None):
    territory.get_area(area_id)
    climate.check_scenario(scenario)
    vs = [v.strip() for v in variables.split(",")] if variables else None
    return {"area_id": area_id, "scenario": scenario, "variables": climate.climate_summary(area_id, scenario, vs)}


@router.get("/{area_id}/series", summary="Serie mensual observada + anomalía")
def area_series(area_id: str, variables: str = "precip,t2m,ndvi",
                date_from: str | None = Query("2015-01", alias="from"), date_to: str | None = Query(None, alias="to"),
                anomaly: bool = True):
    territory.get_area(area_id)
    vs = [v.strip() for v in variables.split(",") if v.strip()]
    out: dict[str, list] = {v: [] for v in vs}
    for r in get_source().monthly_series(area_id, vs, _ym(date_from), _ym(date_to, True)):
        item = {"month": r["month_date"][:7], "value": float(r["value"]) if r.get("value") is not None else None}
        if anomaly:
            item["anomaly"] = float(r["anomaly"]) if r.get("anomaly") is not None else None
        out.setdefault(r["variable_id"], []).append(item)
    return out


@router.get("/{area_id}/hazards", summary="Peligros climáticos mensuales (lluvia, aguaceros, humedad, saturación)")
def area_hazards(area_id: str, date_from: str | None = Query("2015-01", alias="from"),
                 date_to: str | None = Query(None, alias="to")):
    territory.get_area(area_id)
    rows = get_source().monthly_hazard(area_id, _ym(date_from), _ym(date_to, True))
    return [{**{k: v for k, v in r.items() if k not in ("area_id", "computed_at")}, "month": r["month_date"][:7]} for r in rows]


@router.get("/{area_id}/risk", summary="Riesgo de enfermedad por mes y patógeno en el escenario")
def area_risk(area_id: str, scenario: str = "nino", crop: str = "cacao"):
    a = territory.get_area(area_id)
    climate.check_scenario(scenario)
    t = climate.risk_table(area_id, scenario, climate.risk_window(crop, a.get("region")))
    return {"area_id": area_id, "scenario": scenario, **t}


@router.get("/{area_id}/risk/history", summary="Riesgo observado mes a mes + ONI")
def area_risk_history(area_id: str, pathogen: str | None = None,
                      date_from: str | None = Query("2001-01", alias="from"), date_to: str | None = Query(None, alias="to")):
    territory.get_area(area_id)
    f, t = _ym(date_from), _ym(date_to, True)
    oni = {r["month_date"][:7]: float(r["value"]) for r in get_source().enso_index(["oni"], f, t)}
    return [{"month": r["month_date"][:7], "pathogen_id": r["pathogen_id"], "risk_index": float(r["risk_index"]),
             "favorable_days": r.get("favorable_days"), "oni": oni.get(r["month_date"][:7])}
            for r in get_source().risk_monthly(area_id, pathogen, f, t)]


@router.get("/{area_id}/suitability", summary="Aptitud ECOCROP del cultivo por escenario")
def area_suitability(area_id: str, crop: str = "cacao", scenarios: str | None = None):
    territory.get_area(area_id)
    sc = [s.strip() for s in scenarios.split(",")] if scenarios else None
    return [{"scenario": r["scenario_id"], "score": float(r["score"]), "class": r["class"],
             "limiting_factors": r.get("limiting_factors") or [], "details": r.get("details")}
            for r in get_source().suitability(area_id, crop, sc)]


@router.get("/{area_id}/detail", summary="Panel completo del cantón (una sola llamada)")
def area_detail(area_id: str, scenario: str = "nino", crop: str = "cacao"):
    climate.check_scenario(scenario)
    return detail.build(area_id, crop, scenario)
