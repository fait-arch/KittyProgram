"""Fuente 16 — AppEEARS / ECOSTRESS (Fase 3). Requiere EARTHDATA_USER y EARTHDATA_PASS.

Las tareas tardan de minutos a horas: pedir UNA vez, guardar el task_id y descargar después.
Capas verificadas: ECO_L2T_LSTE.002 → LST · ECO_L3T_JET.002 → ETdaily · ECO_L4T_ESI.002 → ESI
"""
from pathlib import Path

import httpx

from app.core.cache import SourceError
from app.core.config import settings

LAYERS = [
    {"product": "ECO_L2T_LSTE.002", "layer": "LST"},
    {"product": "ECO_L3T_JET.002", "layer": "ETdaily"},
    {"product": "ECO_L4T_ESI.002", "layer": "ESI"},
]


def login() -> dict:
    if not settings.earthdata_configured:
        raise SourceError("Faltan EARTHDATA_USER / EARTHDATA_PASS en .env")
    r = httpx.post(f"{settings.APPEEARS_API_URL}/login",
                   auth=(settings.EARTHDATA_USER, settings.EARTHDATA_PASS), timeout=60)
    if r.status_code != 200:
        raise SourceError(f"Login AppEEARS falló: HTTP {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


def submit_area_task(name: str, geojson_geometry: dict, start: str, end: str,
                     layers: list[dict] | None = None) -> str:
    """Fechas en formato MM-DD-YYYY. Devuelve task_id."""
    headers = login()
    task = {
        "task_type": "area", "task_name": name,
        "params": {
            "dates": [{"startDate": start, "endDate": end}],
            "layers": layers or LAYERS,
            "output": {"format": {"type": "geotiff"}, "projection": "geographic"},
            "geo": {"type": "FeatureCollection",
                    "features": [{"type": "Feature", "properties": {}, "geometry": geojson_geometry}]},
        },
    }
    r = httpx.post(f"{settings.APPEEARS_API_URL}/task", json=task, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["task_id"]


def task_status(task_id: str) -> dict:
    r = httpx.get(f"{settings.APPEEARS_API_URL}/task/{task_id}", headers=login(), timeout=60)
    r.raise_for_status()
    return r.json()


def download_bundle(task_id: str, dest_dir: Path | None = None) -> list[Path]:
    headers = login()
    dest = dest_dir or settings.data_raw_path / "appeears" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    files = httpx.get(f"{settings.APPEEARS_API_URL}/bundle/{task_id}",
                      headers=headers, timeout=60).json()["files"]
    saved = []
    for f in files:
        out = dest / f["file_name"].replace("/", "_")
        with httpx.stream("GET", f"{settings.APPEEARS_API_URL}/bundle/{task_id}/{f['file_id']}",
                          headers=headers, timeout=600, follow_redirects=True) as r:
            r.raise_for_status()
            with out.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        saved.append(out)
    return saved
