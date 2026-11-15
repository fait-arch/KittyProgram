"""Descarga VIIRS (verdor, 2012→) y SMAP (humedad del suelo, 2015→ hasta hoy) para país, provincias
y cantones, con el mismo descargador por trozos de ml/etl/gee_daily.py.

    ml/.venv/bin/python -m ml.etl.satellite_extra
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import ee
import pandas as pd

from ml import config
from ml.etl import areas as A
from ml.etl import cantons as C
from ml.etl import gee_daily as G

log = logging.getLogger("satellite_extra")
CURRENT = date.today().year


def _tasks(raw, areas: dict, ds: str, y0: int, y1: int, refresh_current=True):
    G.RAW_DIR = raw
    out = []
    for name, (geom, mask) in areas.items():
        for y in range(y0, y1 + 1):
            p = G.chunk_path(ds, name, y)
            if refresh_current and y == CURRENT and p.exists():
                p.unlink()                                   # año en curso: siempre actualizar
            if not p.exists():
                out.append((ds, name, geom, mask, y))
    return out


def run(workers=8):
    A.init()
    prov = A.get_areas()
    g = pd.read_csv(config.DATA_PROCESSED / "canton_gaul_match.csv", dtype=str).dropna(subset=["gaul_code"])
    meta = pd.read_pickle(config.DATA_PROCESSED / "canton_meta.pkl").set_index("area_name")
    full = ee.Image.constant(1).selfMask().rename("cacao_land")
    cant = {r.id: (C._geom(r.gaul_code), full if bool(meta.mask_fallback.get(r.id, False)) else A.cacao_mask())
            for r in g.itertuples()}
    plan = [(G.RAW_DIR if False else config.DATA_RAW / "gee", prov), (C.RAW, cant)]
    for ds, y0 in (("viirs", 2012), ("smap", 2015)):
        for raw, areas in plan:
            tasks = _tasks(raw, areas, ds, y0, CURRENT)
            G.RAW_DIR = raw
            with ThreadPoolExecutor(workers) as ex:
                bad = sum(1 for f in as_completed([ex.submit(G.fetch_chunk, *t) for t in tasks]) if f.exception())
            log.info("%s · %s: %d trozos, fallos %d", ds, raw.name, len(tasks), bad)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    run()
