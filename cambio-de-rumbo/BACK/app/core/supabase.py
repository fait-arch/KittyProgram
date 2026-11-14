"""Clientes de Supabase (ver BACK/docs/01-arquitectura.md).

- service_client(): service_role → ETL, ML, caché. Salta RLS. SOLO servidor.
- user_client(jwt): anon + JWT del usuario → CRUD del agricultor con RLS.
"""
from functools import lru_cache

import httpx

from app.core.config import settings


@lru_cache
def service_client():
    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def user_client(jwt: str):
    from supabase import create_client

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(jwt)
    return client


def check_supabase() -> tuple[bool, str | None]:
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return False, "Faltan SUPABASE_URL o SUPABASE_ANON_KEY"
    try:
        r = httpx.get(f"{settings.SUPABASE_URL}/auth/v1/settings",
                      headers={"apikey": settings.SUPABASE_ANON_KEY}, timeout=10)
        return r.status_code == 200, None if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]
