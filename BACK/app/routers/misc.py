"""Punto libre (NASA POWER), observaciones de campo y administración."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..core import cache
from ..core.auth import CurrentUser, get_current_user, require_admin
from ..core.errors import bad_request
from ..data import get_source
from ..services import climate, power, predictor, territory

router = APIRouter(tags=["otros"])


@router.get("/point/climate", summary="Clima de un punto cualquiera (NASA POWER) + chequeo vs requerimientos")
def point_climate(lat: float = Query(..., ge=-6, le=2.5), lon: float = Query(..., ge=-92.5, le=-74.5), crop: str = "cacao"):
    lat, lon = round(lat, 2), round(lon, 2)
    data = power.climatology(lat, lon)
    clim = {"t2m": {"annual": data["annual"]["t2m"]}, "precip": {"annual": data["annual"]["precip_mm"]}}
    static = {"elevation_mean_m": data.get("elevation_m")}
    try:
        canton = territory.lookup(lat, lon)
    except Exception:  # noqa: BLE001 — sin cantones cargados no se bloquea el clima
        canton = None
    return {**data, "canton": (canton or {}).get("canton"), "province": (canton or {}).get("province"),
            "requirement_check": climate.requirement_check(crop, clim, static),
            "warning": "Celda de ~55 km: en la Costa puede subestimar la temperatura y asumir una altitud mayor. "
                       "Si el punto cae en un cantón con datos, usar /areas/{id}/detail como fuente principal."}


@router.get("/observations", summary="Observaciones de campo (GBIF, técnicos, agricultores)")
def list_observations(area_id: str | None = None, pathogen: str | None = None,
                      source: str | None = Query(None, pattern="^(gbif|tecnico|agricultor)$"),
                      limit: int = Query(200, ge=1, le=1000)):
    return get_source().observations(area_id, pathogen, source, limit)


class ObservationIn(BaseModel):
    pathogen_id: str | None = None
    observed_on: date
    lat: float = Field(..., ge=-6, le=2.5)
    lon: float = Field(..., ge=-92.5, le=-74.5)
    pods_total: int | None = Field(None, ge=0)
    pods_diseased: int | None = Field(None, ge=0)
    severity: int | None = Field(None, ge=0, le=5)
    role: str = Field("agricultor", pattern="^(agricultor|tecnico)$")
    notes: str | None = Field(None, max_length=2000)


@router.post("/observations", status_code=201, summary="Registrar observación de campo (requiere login)")
def create_observation(body: ObservationIn, user: CurrentUser = Depends(get_current_user)):
    if body.pods_total is not None and body.pods_diseased is not None and body.pods_diseased > body.pods_total:
        raise bad_request("invalid_pods", "pods_diseased no puede ser mayor que pods_total")
    try:
        hit = territory.lookup(body.lat, body.lon)
    except Exception:  # noqa: BLE001
        hit = None
    row = {"area_id": (hit or {}).get("canton", {}).get("id"), "pathogen_id": body.pathogen_id,
           "observed_on": body.observed_on.isoformat(), "lat": body.lat, "lon": body.lon,
           "pods_total": body.pods_total, "pods_diseased": body.pods_diseased, "severity": body.severity,
           "source": body.role, "observer_id": user.id, "notes": body.notes}
    return get_source().insert_observation(user.token, row)


@router.post("/admin/cache/clear", summary="Vaciar caché (ML lo llama tras predecir)")
def admin_cache_clear(_: str = Depends(require_admin)):
    return {"cleared_entries": cache.clear_all()}


@router.post("/admin/model/reload", summary="Recargar el .joblib del modelo")
def admin_model_reload(_: str = Depends(require_admin)):
    st = predictor.load()
    cache.clear_all()
    return st
