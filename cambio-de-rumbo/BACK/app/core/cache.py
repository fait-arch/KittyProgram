"""Caché simple en disco (JSON) y descargas HTTP con reintento."""
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from app.core.config import settings


def _path(namespace: str, key: str) -> Path:
    safe = hashlib.sha1(key.encode()).hexdigest()[:16]
    return settings.cache_path / namespace / f"{safe}.json"


def cached(namespace: str, key: str, producer: Callable[[], Any], use_cache: bool = True) -> Any:
    """Devuelve el valor guardado si es reciente; si no, llama a producer() y lo guarda."""
    path = _path(namespace, key)
    ttl = settings.CACHE_TTL_HOURS * 3600
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text(encoding="utf-8"))
    value = producer()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value


def http_get(url: str, *, params: dict | None = None, timeout: int | None = None,
             retries: int = 2, **kwargs) -> httpx.Response:
    """GET con reintentos (NASA POWER y NOAA a veces tardan o cortan)."""
    timeout = timeout or settings.HTTP_TIMEOUT_SECONDS
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = httpx.get(url, params=params, timeout=timeout, follow_redirects=True, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPError as exc:
            last = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise SourceError(f"Fallo al consultar {url}: {last}") from last


def download(url: str, dest: Path, timeout: int = 600) -> Path:
    """Descarga un archivo grande a disco (ej. ZIP de FAOSTAT)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    return dest


class SourceError(Exception):
    """Error al obtener datos de una fuente externa."""
