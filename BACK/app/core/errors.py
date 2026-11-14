"""Errores de la API con un `code` estable para el frontend."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail


def not_found(code: str, detail: str) -> ApiError:
    return ApiError(404, code, detail)


def bad_request(code: str, detail: str) -> ApiError:
    return ApiError(400, code, detail)


def unavailable(code: str, detail: str) -> ApiError:
    return ApiError(503, code, detail)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail, "code": exc.code})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Errores de PostgREST / red: no exponer detalles internos.
        name = type(exc).__name__
        if name in {"ConnectError", "ConnectTimeout", "ReadTimeout", "RemoteProtocolError"}:
            return JSONResponse(status_code=503, content={"detail": f"Base de datos no disponible ({name})", "code": "database_unreachable"})
        if name == "APIError":   # PostgREST: tabla/vista inexistente, RLS, etc.
            return JSONResponse(status_code=502, content={"detail": f"Error de la base de datos: {exc}"[:300], "code": "database_error"})
        return JSONResponse(status_code=500, content={"detail": f"Error interno ({name})", "code": "internal_error"})
