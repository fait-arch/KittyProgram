"""SMAP L4 diario por cantón, en lote: una consulta por mes que reduce los 125 cantones a la vez.

(El descargador por cantón y año de gee_daily es demasiado lento para SMAP: 8 imágenes por día.)

    ml/.venv/bin/python -m ml.etl.smap_cantons      → data/raw/gee_cantons/smap_batch/YYYY_MM.parquet
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import ee
import pandas as pd

from ml import config
from ml.etl import areas as A
from ml.etl.cantons import _geom
from ml.etl.gee_daily import _with_retry

COL = "NASA/SMAP/SPL4SMGP/008"
OUT = config.DATA_RAW / "gee_cantons" / "smap_batch"
log = logging.getLogger("smap_cantons")


def canton_fc() -> ee.FeatureCollection:
    g = pd.read_csv(config.DATA_PROCESSED / "canton_gaul_match.csv", dtype=str).dropna(subset=["gaul_code"])
    return ee.FeatureCollection([ee.Feature(_geom(r.gaul_code).simplify(1000), {"area_name": r.id})
                                 for r in g.itertuples()])


def month_rows(fc, y: int, m: int) -> list[dict]:
    start = ee.Date(date(y, m, 1).isoformat())
    n = (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days
    col = ee.ImageCollection(COL).select("sm_surface")
    last = ee.Date(col.sort("system:time_start", False).first().get("system:time_start"))
    avail = int(last.difference(start, "day").getInfo())        # mes en curso: solo días con datos
    n = max(0, min(n, avail))

    def per_day(i):
        d0 = start.advance(i, "day")
        img = col.filterDate(d0, d0.advance(1, "day")).mean().rename("sm")
        return img.reduceRegions(fc, ee.Reducer.mean(), 9000, tileScale=2) \
                  .map(lambda f: f.set("date", d0.format("YYYY-MM-dd")))

    feats = ee.FeatureCollection(ee.List.sequence(0, n - 1).map(per_day)).flatten()
    res = feats.select(["area_name", "date", "mean"], retainGeometry=False).getInfo()["features"]
    return [{"area_name": f["properties"]["area_name"], "date": f["properties"]["date"],
             "smap_sm_surface_m3m3": f["properties"].get("mean")} for f in res]


def main(workers=6):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    A.init()
    fc = canton_fc()
    today = date.today()
    months = [(y, m) for y in range(2015, today.year + 1) for m in range(1, 13)
              if (y, m) >= (2015, 4) and date(y, m, 1) <= today]
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [(y, m) for y, m in months
            if not (OUT / f"{y}_{m:02d}.parquet").exists() or (y, m) == (today.year, today.month)]

    def job(y, m):
        rows = _with_retry(lambda: month_rows(fc, y, m), f"{y}-{m:02d}")
        pd.DataFrame(rows).to_parquet(OUT / f"{y}_{m:02d}.parquet", index=False)

    bad = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(job, *t): t for t in todo}
        for i, f in enumerate(as_completed(futs), 1):
            if f.exception():
                bad += 1
                log.error("FALLO %s: %s", futs[f], str(f.exception())[:200])
            if i % 20 == 0:
                log.info("%d/%d", i, len(todo))
    log.info("terminado: %d meses, fallos %d", len(todo), bad)


if __name__ == "__main__":
    main()
