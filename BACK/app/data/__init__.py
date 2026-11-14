"""Selección de la fuente de datos según DATA_SOURCE (supabase | mock)."""
from functools import lru_cache

from ..core.config import get_settings


@lru_cache
def get_source():
    if get_settings().data_source == "supabase":
        from .supabase_source import SupabaseSource
        return SupabaseSource()
    from .mock_source import MockSource
    return MockSource()
