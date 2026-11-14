"""Clientes de Supabase. Lecturas: anon/publishable (RLS = lectura pública); si falta, la secreta."""
import logging
from functools import lru_cache

from supabase import Client, create_client

from .config import get_settings
from .errors import unavailable

log = logging.getLogger(__name__)


def read_key() -> tuple[str, str]:
    s = get_settings()
    if s.supabase_anon_key:
        return s.supabase_anon_key, "publishable"
    if s.supabase_secret_key:
        return s.supabase_secret_key, "secret"
    return "", "none"


@lru_cache
def anon_client() -> Client:
    s = get_settings()
    key, kind = read_key()
    if not s.supabase_url or not key:
        raise unavailable("supabase_not_configured", "Falta SUPABASE_URL o una key de Supabase en BACK/.env")
    if kind == "secret":
        log.warning("Leyendo Supabase con la clave SECRETA (salta RLS). Usar la publishable cuando esté disponible.")
    return create_client(s.supabase_url, key)


def user_client(token: str) -> Client:
    """Actúa como el usuario: RLS decide qué puede escribir. Requiere la publishable/anon."""
    s = get_settings()
    if not s.supabase_url or not s.supabase_anon_key:
        raise unavailable("supabase_not_configured", "Para escribir como usuario hace falta SUPABASE_ANON_KEY (publishable)")
    c = create_client(s.supabase_url, s.supabase_anon_key)
    c.postgrest.auth(token)
    return c
