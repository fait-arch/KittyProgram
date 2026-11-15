"""Proyecciones NASA NEX-GDDP-CMIP6 (GEE) por área: medias mensuales de cada año.

Modelos ACCESS-CM2, EC-Earth3, GFDL-ESM4, MRI-ESM2-0 (los del plan del equipo), r1i1p1f1.
    histórico 1995–2014 · SSP2-4.5 y SSP5-8.5 2015–2060
Variables: tas, tasmax, tasmin (°C), hurs (%), pr (mm/día). Áreas: país, provincias (ml.etl.areas)
y cantones (GAUL nivel 2, id = uuid de Supabase). Sin máscara de altitud (rejilla de ~25 km).

    ml/.venv/bin/python -m ml.etl.cmip6        → data/processed/cmip6_monthly.parquet
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import ee
import pandas as pd

from ml import config
from ml.etl import areas as A
from ml.etl.cantons import _geom
from ml.etl.gee_daily import _with_retry

COL = "NASA/GDDP-CMIP6"
MODELS = ["ACCESS-CM2", "EC-Earth3", "GFDL-ESM4", "MRI-ESM2-0"]
RUNS = [("historical", y) for y in range(1995, 2015)] + \
       [(s, y) for s in ("ssp245", "ssp585") for y in range(2015, 2061)]
BANDS = ["tas", "tasmax", "tasmin", "hurs", "pr"]
RAW = config.DATA_RAW / "gee_cmip6"
OUT = config.DATA_PROCESSED / "cmip6_monthly.parquet"
log = logging.getLogger("cmip6")


def area_fc() -> ee.FeatureCollection:
    feats = [ee.Feature(g, {"area_name": n}) for n, (g, _) in A.get_areas().items()]
    g = pd.read_csv(config.DATA_PROCESSED / "canton_gaul_match.csv", dtype=str).dropna(subset=["gaul_code"])
    feats += [ee.Feature(_geom(r.gaul_code), {"area_name": r.id}) for r in g.itertuples()]
    return ee.FeatureCollection(feats)


def year_image(model: str, scenario: str, year: int) -> ee.Image:
    c = (ee.ImageCollection(COL).filter(ee.Filter.eq("model", model)).filter(ee.Filter.eq("scenario", scenario))
         .filterDate(f"{year}-01-01", f"{year + 1}-01-01").select(BANDS))
    out = []
    for m in range(1, 13):
        img = c.filter(ee.Filter.calendarRange(m, m, "month")).mean()
        t = img.select(["tas", "tasmax", "tasmin"]).subtract(273.15)
        out.append(t.addBands(img.select("hurs")).addBands(img.select("pr").multiply(86400))
                   .rename([f"{b}_{m:02d}" for b in BANDS]))
    return ee.Image.cat(out)


def fetch(fc, model, scenario, year) -> str:
    path = RAW / f"{model}_{scenario}_{year}.parquet"
    if path.exists():
        return "cached"
    res = _with_retry(lambda: year_image(model, scenario, year).reduceRegions(
        fc, ee.Reducer.mean(), 27830, tileScale=4).getInfo(), f"{model}/{scenario}/{year}")
    rows = []
    for f in res["features"]:
        p = f["properties"]
        for m in range(1, 13):
            rows.append({"area_name": p["area_name"], "model": model, "scenario": scenario, "year": year, "month": m,
                         **{b: p.get(f"{b}_{m:02d}") for b in BANDS}})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return "done"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    A.init()
    fc = area_fc()
    tasks = [(m, s, y) for m in MODELS for s, y in RUNS]
    done = bad = 0
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fetch, fc, *t): t for t in tasks}
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                bad += 1
                log.error("FALLO %s: %s", futs[f], str(e)[:200])
            if done % 40 == 0:
                log.info("%d/%d (fallos %d)", done, len(tasks), bad)
    df = pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob("*.parquet"))], ignore_index=True)
    df.to_parquet(OUT, index=False)
    log.info("escrito %s: %d filas, %d áreas, fallos %d", OUT, len(df), df.area_name.nunique(), bad)


if __name__ == "__main__":
    main()
