"""Fuente 9 — ECOCROP (FAO): requerimientos del cultivo. CSV en GitHub, sin cuenta.

Destino: `crop_requirements`.
"""
import csv
import io

from app.core.cache import SourceError, cached, http_get
from app.core.config import settings

# Columnas útiles del CSV → nombre legible
FIELDS = {
    "TOPMN": "temp_opt_min_c", "TOPMX": "temp_opt_max_c",
    "TMIN": "temp_abs_min_c", "TMAX": "temp_abs_max_c",
    "ROPMN": "lluvia_opt_min_mm", "ROPMX": "lluvia_opt_max_mm",
    "RMIN": "lluvia_abs_min_mm", "RMAX": "lluvia_abs_max_mm",
    "PHOPMN": "ph_opt_min", "PHOPMX": "ph_opt_max",
    "PHMIN": "ph_abs_min", "PHMAX": "ph_abs_max",
    "ALTMX": "altitud_max_m", "KTMP": "temp_letal_c",
    "GMIN": "ciclo_min_dias", "GMAX": "ciclo_max_dias",
}


def _num(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "", "NA") else None
    except ValueError:
        return None


def _rows() -> list[dict]:
    def _get():
        content = http_get(settings.ECOCROP_CSV_URL, timeout=60).content.decode("latin-1")
        return list(csv.DictReader(io.StringIO(content)))

    return cached("ecocrop", "db", _get)


def get_requirements(scientific_name: str | None = None) -> dict:
    name = (scientific_name or settings.CROP_SCIENTIFIC_NAME).strip().lower()
    rows = _rows()
    row = next((r for r in rows if r.get("ScientificName", "").strip().lower() == name), None)
    if row is None:  # búsqueda parcial, ej. "cacao"
        row = next((r for r in rows if name in r.get("ScientificName", "").lower()
                    or name in r.get("COMNAME", "").lower()), None)
    if row is None:
        raise SourceError(f"'{name}' no está en ECOCROP")
    out = {"cientifico": row.get("ScientificName"), "fuente": "FAO ECOCROP"}
    out.update({nuevo: _num(row.get(col)) for col, nuevo in FIELDS.items()})
    return out


def search(text: str, limit: int = 20) -> list[str]:
    t = text.lower()
    return [r["ScientificName"] for r in _rows()
            if t in r.get("ScientificName", "").lower() or t in r.get("COMNAME", "").lower()][:limit]
