"""Caché en memoria con TTL. Clave = nombre + argumentos normalizados."""
import functools
import json
import threading
from typing import Any, Callable

from cachetools import TTLCache

_caches: list[TTLCache] = []
_lock = threading.RLock()


def _key(name: str, args: tuple, kwargs: dict) -> str:
    return name + json.dumps([args, sorted(kwargs.items())], default=str, sort_keys=True)


def cached(ttl: int, maxsize: int = 2048) -> Callable:
    """Decorador: memoriza el resultado de funciones puras de lectura."""
    store: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
    _caches.append(store)

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            k = _key(fn.__qualname__, args, kwargs)
            with _lock:
                if k in store:
                    return store[k]
            value = fn(*args, **kwargs)
            with _lock:
                store[k] = value
            return value

        wrapper.cache_store = store  # type: ignore[attr-defined]
        return wrapper

    return deco


def clear_all() -> int:
    with _lock:
        n = sum(len(c) for c in _caches)
        for c in _caches:
            c.clear()
    return n
