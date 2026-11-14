"""Fuente 14 — GBIF: ocurrencias de patógenos (ej. Moniliophthora roreri). Sin cuenta.

Sirve para validar que el índice de riesgo es alto donde la enfermedad fue observada.
Destino: `field_observations` (Fase 3).
"""
from app.core.cache import cached, http_get
from app.core.config import settings

PATHOGENS = {
    "monilia": "Moniliophthora roreri",
    "mazorca_negra": "Phytophthora palmivora",
    "escoba_bruja": "Moniliophthora perniciosa",
}


def fetch_occurrences(pathogen_id: str = "monilia", country: str = "EC",
                      max_records: int = 1000, use_cache: bool = True) -> list[dict]:
    scientific = PATHOGENS.get(pathogen_id, pathogen_id)

    def _get():
        out, offset = [], 0
        while offset < max_records:
            r = http_get(f"{settings.GBIF_API_URL}/occurrence/search", timeout=30, params={
                "scientificName": scientific, "country": country,
                "hasCoordinate": "true", "limit": 300, "offset": offset}).json()
            for o in r.get("results", []):
                if "decimalLatitude" not in o:
                    continue
                out.append({"external_id": str(o["key"]), "lat": o["decimalLatitude"],
                            "lon": o["decimalLongitude"], "observed_on": (o.get("eventDate") or "")[:10],
                            "source": "gbif", "pathogen_id": pathogen_id})
            if r.get("endOfRecords", True):
                break
            offset += 300
        return out

    return cached("gbif", f"{scientific}:{country}:{max_records}", _get, use_cache)
