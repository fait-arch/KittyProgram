"""Experimento 1 — horas de hoja mojada (ERA5-Land HORARIO, GEE), ene–jun 1961–2025.

Los hongos del cacao infectan cuando la mazorca pasa HORAS seguidas mojada. El promedio diario
de HR borra eso, así que se cuentan horas por píxel y se promedian en el área:

    HR_h        = 100·e°(Td)/e°(T)                     (Magnus, por hora y píxel)
    wet_h       = Σ_horas 1[HR ≥ 90 %]                  (hoja mojada)
    infect_h    = Σ_horas 1[HR ≥ 90 % ∧ 20 ≤ T ≤ 28 °C] (ventana térmica de Moniliophthora/Phytophthora)
    night_wet_h = Σ_horas nocturnas (19–06 h local = 00–11 UTC) 1[HR ≥ 90 %]

Se agrega por MES en el servidor (una suma de ~720 imágenes) y se guarda por área y mes.
No toca nada del modelo: escribe data/processed/hourly_wetness.parquet.

    ml/.venv/bin/python -m ml.experiments.hourly_wetness [--workers 8]
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import ee
import pandas as pd

from ml import config
from ml.etl import areas as areas_mod
from ml.etl.gee_daily import _with_retry

COL = "ECMWF/ERA5_LAND/HOURLY"
RAW = config.DATA_RAW / "gee" / "era5_hourly_wet"
OUT = config.DATA_PROCESSED / "hourly_wetness.parquet"
MONTHS = range(1, 7)
log = logging.getLogger("hourly_wetness")


def _flags(img: ee.Image) -> ee.Image:
    t = img.select("temperature_2m").subtract(273.15)
    td = img.select("dewpoint_temperature_2m").subtract(273.15)
    es = lambda x: x.multiply(17.27).divide(x.add(237.3)).exp()
    rh = es(td).divide(es(t)).multiply(100)
    wet = rh.gte(90)
    hour = ee.Number(img.date().get("hour"))
    night = ee.Image.constant(ee.Algorithms.If(hour.lt(12), 1, 0))
    return ee.Image.cat([wet, wet.And(t.gte(20)).And(t.lte(28)), wet.multiply(night)]) \
        .rename(["wet_h", "infect_h", "night_wet_h"]).toFloat()


def month_row(geom, mask, year: int, month: int) -> dict:
    start = ee.Date(date(year, month, 1).isoformat())
    img = ee.ImageCollection(COL).filterDate(start, start.advance(1, "month")) \
        .select(["temperature_2m", "dewpoint_temperature_2m"]).map(_flags).sum()
    v = img.updateMask(mask).reduceRegion(ee.Reducer.mean(), geom, 11000, bestEffort=True,
                                          maxPixels=1e9, tileScale=4).getInfo()
    return {"year": year, "month": month, **v}


def fetch(area: str, geom, mask, year: int) -> str:
    path = RAW / f"{areas_mod.slug(area)}_{year}.parquet"
    if path.exists():
        return "cached"
    rows = [_with_retry(lambda m=m: month_row(geom, mask, year, m), f"{area}/{year}/{m}") for m in MONTHS]
    df = pd.DataFrame(rows).assign(area_name=area)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return "done"


def combine() -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(f) for f in sorted(RAW.glob("*.parquet"))], ignore_index=True)
    yr = df.groupby(["area_name", "year"])[["wet_h", "infect_h", "night_wet_h"]].sum().reset_index()
    yr.to_parquet(OUT, index=False)
    return yr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--areas", default="")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    areas_mod.init()
    areas = areas_mod.get_areas()
    keep = set(config.PROVINCES + ["national"]) if not a.areas else set(a.areas.split(","))
    tasks = [(n, g, m, y) for n, (g, m) in areas.items() if n in keep
             for y in range(config.YEAR_START, config.YEAR_END + 1)]
    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(fetch, *t): t for t in tasks}
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                log.error("FALLO %s: %s", futs[f][:1] + futs[f][3:], str(e)[:200])
            if done % 50 == 0:
                log.info("%d/%d", done, len(tasks))
    yr = combine()
    log.info("escrito %s: %d filas", OUT, len(yr))


if __name__ == "__main__":
    main()
