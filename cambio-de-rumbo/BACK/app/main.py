"""API FastAPI.

Regla del proyecto (docs/03-backend.md): la API de producción NO calcula en vivo con GEE;
lee resultados del ETL en Supabase. Los endpoints /dev/* existen solo para probar las fuentes
mientras se construye el ETL, y se desactivan con APP_ENV=production.
"""
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core import gee
from app.core.cache import SourceError
from app.core.config import settings
from app.core.supabase import check_supabase
from app.sources import ecocrop, gbif, gee_data, noaa, power

app = FastAPI(title="CacaoResiliente API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])

SOURCES = [
    {"id": 1, "nombre": "NOAA CPC — ONI", "acceso": "HTTP texto", "cuenta": False, "fase": 1},
    {"id": 2, "nombre": "NOAA CPC — Niño 1+2", "acceso": "HTTP texto", "cuenta": False, "fase": 1},
    {"id": 3, "nombre": "ERA5-Land diario", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 4, "nombre": "GPM IMERG", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 5, "nombre": "SMAP L4", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 6, "nombre": "MODIS NDVI", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 7, "nombre": "SRTM, OpenLandMap, WorldCover", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 8, "nombre": "FAO GAUL (límites)", "acceso": "GEE", "cuenta": True, "fase": 1},
    {"id": 9, "nombre": "ECOCROP", "acceso": "CSV GitHub", "cuenta": False, "fase": 1},
    {"id": 10, "nombre": "ESPAC (INEC)", "acceso": "Descarga manual XLSX", "cuenta": False, "fase": 1},
    {"id": 11, "nombre": "FAOSTAT", "acceso": "ZIP masivo", "cuenta": False, "fase": 1},
    {"id": 12, "nombre": "SIPA (MAG)", "acceso": "Descarga manual", "cuenta": False, "fase": 1},
    {"id": 13, "nombre": "NASA POWER", "acceso": "API REST", "cuenta": False, "fase": 1},
    {"id": 14, "nombre": "GBIF", "acceso": "API REST", "cuenta": False, "fase": 3},
    {"id": 15, "nombre": "NEX-GDDP-CMIP6", "acceso": "GEE", "cuenta": True, "fase": 2},
    {"id": 16, "nombre": "ECOSTRESS (AppEEARS)", "acceso": "API Earthdata", "cuenta": True, "fase": 3},
]


@app.on_event("startup")
def _startup() -> None:
    faltan = settings.missing_required()
    if faltan:
        print(f"⚠️  Variables faltantes en .env: {', '.join(faltan)}")
    gee.init_gee()
    print("GEE listo ✅" if gee.GEE_READY else f"GEE en modo degradado ⚠️  {gee.GEE_ERROR}")


@app.get("/health")
def health() -> dict:
    supa_ok, supa_err = check_supabase()
    return {"status": "ok", "gee_ready": gee.GEE_READY, "gee_error": gee.GEE_ERROR,
            "supabase_ready": supa_ok, "supabase_error": supa_err,
            "earthdata_configured": settings.earthdata_configured,
            "missing_env": settings.missing_required()}


api = APIRouter(prefix="/api/v1")


@api.get("/meta")
def meta() -> dict:
    return {"cultivo": settings.CROP_SCIENTIFIC_NAME, "provincias": settings.provinces,
            "fuentes": SOURCES,
            "atribucion": "NASA (GPM, SMAP, GLDAS, MODIS, SRTM, NEX-GDDP-CMIP6, POWER, ECOSTRESS) · "
                          "Contains modified Copernicus Climate Change Service information (ERA5-Land) · "
                          "NOAA CPC · INEC (ESPAC) · FAO (FAOSTAT, ECOCROP, GAUL) · MAG (SIPA) · "
                          "GBIF.org · ISRIC/OpenLandMap · ESA WorldCover"}


app.include_router(api)

# ── Endpoints de desarrollo: probar cada fuente ────────────────────────
dev = APIRouter(prefix="/dev", tags=["dev (probar fuentes)"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RuntimeError as exc:  # GEE no disponible
        raise HTTPException(503, str(exc)) from exc
    except (SourceError, FileNotFoundError) as exc:
        raise HTTPException(502, str(exc)) from exc


@dev.get("/enso")
def dev_enso():
    return _run(noaa.enso_current)


@dev.get("/ecocrop")
def dev_ecocrop(name: str = Query(None, description="Ej. 'Theobroma cacao' (por defecto el del .env)")):
    return _run(ecocrop.get_requirements, name)


@dev.get("/power/climatology")
def dev_power_clim(lat: float = Query(-1.80, ge=-90, le=90), lon: float = Query(-79.53, ge=-180, le=180)):
    return _run(power.power_climatology, lat, lon)


@dev.get("/power/monthly")
def dev_power_monthly(lat: float = -1.80, lon: float = -79.53, start: int = 2020, end: int = 2024):
    return _run(power.power_monthly, lat, lon, start, end)


@dev.get("/gbif")
def dev_gbif(pathogen: str = Query("monilia", description="monilia | mazorca_negra | escoba_bruja")):
    rows = _run(gbif.fetch_occurrences, pathogen)
    return {"total": len(rows), "muestra": rows[:20]}


@dev.get("/gee/cantons")
def dev_cantons(province: str = Query("Los Rios", description="Nombre GAUL, sin tildes")):
    return _run(gee_data.canton_list, [province])


@dev.get("/gee/monthly")
def dev_gee_monthly(lat: float = -1.80, lon: float = -79.53, year: int = 2023):
    return _run(lambda: gee_data.monthly_series(gee_data.point_area(lat, lon), year))


@dev.get("/gee/static")
def dev_gee_static(lat: float = -1.80, lon: float = -79.53):
    return _run(lambda: gee_data.static_features(gee_data.point_area(lat, lon)))


if settings.APP_ENV != "production":
    app.include_router(dev)
