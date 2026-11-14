"""Inicialización de Google Earth Engine (modo degradado si falla)."""
from app.core.config import settings

GEE_READY = False
GEE_ERROR: str | None = None


def init_gee() -> bool:
    global GEE_READY, GEE_ERROR
    if not settings.gee_configured:
        GEE_READY, GEE_ERROR = False, "GEE_PROJECT no está configurado en .env"
        return False
    try:
        import ee

        if settings.gee_uses_service_account:
            if settings.GEE_PRIVATE_KEY_JSON:
                creds = ee.ServiceAccountCredentials(settings.GEE_SERVICE_ACCOUNT,
                                                     key_data=settings.GEE_PRIVATE_KEY_JSON)
            else:
                creds = ee.ServiceAccountCredentials(settings.GEE_SERVICE_ACCOUNT,
                                                     settings.GEE_PRIVATE_KEY_PATH)
            ee.Initialize(creds, project=settings.GEE_PROJECT)
        else:
            ee.Initialize(project=settings.GEE_PROJECT)  # usa `earthengine authenticate`
        ee.Number(1).getInfo()
        GEE_READY, GEE_ERROR = True, None
    except Exception as exc:  # noqa: BLE001
        GEE_READY, GEE_ERROR = False, str(exc)[:400]
    return GEE_READY


def require_gee() -> None:
    """Lanza un error claro si GEE no está listo (los routers lo convierten en 503)."""
    if not GEE_READY and not init_gee():
        raise RuntimeError(f"Earth Engine no disponible: {GEE_ERROR}")
