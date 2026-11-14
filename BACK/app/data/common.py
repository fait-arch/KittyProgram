"""Utilidades compartidas por las fuentes de datos."""
import unicodedata
import uuid
from typing import Any

from shapely import wkb
from shapely.geometry import mapping


def name_key(name: str) -> str:
    """Igual que areas.name_key en la BD: minúsculas y sin tildes."""
    s = unicodedata.normalize("NFKD", name)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def to_geojson(geom: Any) -> dict | None:
    """PostgREST devuelve PostGIS como GeoJSON (PostGIS ≥ 3) o como WKB hex; normaliza a GeoJSON."""
    if geom is None:
        return None
    if isinstance(geom, dict):
        return geom
    if isinstance(geom, str):
        return mapping(wkb.loads(geom, hex=True))
    raise ValueError(f"Formato de geometría desconocido: {type(geom).__name__}")
