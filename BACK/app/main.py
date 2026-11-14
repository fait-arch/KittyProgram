"""CacaoResiliente — backend integrador (FastAPI)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.errors import install_handlers
from .core.supabase import read_key
from .data import get_source
from .routers import advice, areas, catalog, enso, losses, misc
from .services import insights, predictor

VERSION = "0.1.0"
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    predictor.load()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="CacaoResiliente API",
        version=VERSION,
        description="¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades asociadas "
                    "a El Niño, hoy y con el clima de 2050? Contrato: docs/backend/02-endpoints.md",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["*"], allow_headers=["*"])
    install_handlers(app)

    @app.middleware("http")
    async def data_source_header(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Data-Source"] = s.data_source
        if request.method == "GET" and resp.status_code == 200 and "cache-control" not in resp.headers:
            resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @app.get("/health", tags=["sistema"])
    def health():
        src = get_source()
        try:
            db_ok = src.ping()
            db_err = None
        except Exception as e:  # noqa: BLE001 — /health nunca falla
            db_ok, db_err = False, f"{type(e).__name__}: {e}"[:300]
        model = predictor.status()
        ok = db_ok and (model["loaded"] or src.name == "mock")
        return {"status": "ok" if ok else "degraded", "version": VERSION, "data_source": src.name,
                "database": {"ok": db_ok, "error": db_err, "key_type": read_key()[1] if src.name == "supabase" else None},
                "model": model,
                "ai": {"provider": s.ai_provider, "model": s.ai_model_name, "configured": insights.configured()}}

    for r in (catalog.router, enso.router, areas.router, losses.router, advice.router, misc.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
