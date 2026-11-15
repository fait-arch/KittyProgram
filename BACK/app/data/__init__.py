"""Selección de la fuente de datos según DATA_SOURCE (supabase | mock)."""
from functools import lru_cache

from ..core.config import get_settings


@lru_cache
def get_source():
    s = get_settings()
    if s.data_source == "supabase":
        from .supabase_source import SupabaseSource
        src = SupabaseSource()
        if s.ml_artifacts_fallback:
            # predicciones del modelo entrenado (ml/artifacts) para los escenarios sin filas en la base
            from .model_artifacts import ArtifactBackedSource
            return ArtifactBackedSource(src)
        return src
    from .mock_source import MockSource
    return MockSource()
