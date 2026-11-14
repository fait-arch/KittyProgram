"""Daily climate per cacao province (masked to < 900 m) from Google Earth Engine.

Datasets (area mean per day, masked to cacao-relevant land):
  era5  ECMWF/ERA5_LAND/DAILY_AGGR        1950→   (T, Tmax, Tmin, Td, precip, soil water L1/L2, SSRD, wind)
  gpm   NASA/GPM_L3/IMERG_V07 (30 min)    1998→   daily precip = Σ(mm/h) × 0.5, UTC days
  gldas NASA/GLDAS/V021/NOAH/G025/T3H     2000→   daily mean RootMoist_inst, SoilMoi0_10cm_inst
  smap  NASA/SMAP/SPL4SMGP/008            2015-03→ daily mean sm_surface, sm_rootzone

Each (dataset, area, year) chunk is one server-side aggregation + getInfo, cached to
ml/data/raw/gee/{dataset}/{area_slug}_{year}.parquet (reruns skip cached chunks).
If a full-year request fails repeatedly (timeout / memory), it is split into months.
Final output: ml/data/processed/climate_daily.parquet (wide: date, area_name, variables).

Run:
    ml/.venv/bin/python -m ml.etl.gee_daily [--start-year 1961 --end-year 2025]
        [--areas "Los Rios,national"] [--datasets era5,gpm,gldas,smap] [--workers 8]
        [--combine-only]
"""
from __future__ import annotations

import argparse
import logging
import math
import random
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import ee
import numpy as np
import pandas as pd

from ml import config
from ml.etl import areas as areas_mod

warnings.filterwarnings("ignore", category=DeprecationWarning)
log = logging.getLogger("gee_daily")

RAW_DIR = config.DATA_RAW / "gee"
OUT_PATH = config.DATA_PROCESSED / "climate_daily.parquet"

# ---------------------------------------------------------------- dataset specs
DATASETS = {
    "era5": dict(
        collection="ECMWF/ERA5_LAND/DAILY_AGGR", first=date(1950, 1, 2), scale=9000, kind="daily",
        bands=["temperature_2m", "temperature_2m_max", "temperature_2m_min",
               "dewpoint_temperature_2m", "total_precipitation_sum",
               "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
               "surface_solar_radiation_downwards_sum",
               "u_component_of_wind_10m", "v_component_of_wind_10m"],
    ),
    "gpm": dict(collection="NASA/GPM_L3/IMERG_V07", first=date(1998, 1, 1), scale=11000,
                kind="sum_halfhour", bands=["precipitation"]),
    "gldas": dict(collection="NASA/GLDAS/V021/NOAH/G025/T3H", first=date(2000, 1, 1), scale=11000,
                  kind="mean", bands=["RootMoist_inst", "SoilMoi0_10cm_inst"]),
    "smap": dict(collection="NASA/SMAP/SPL4SMGP/008", first=date(2015, 3, 31), scale=11000,
                 kind="mean", bands=["sm_surface", "sm_rootzone"]),
}
PRIORITY = ["era5", "gpm", "gldas", "smap"]


def _era5_prep(img: ee.Image) -> ee.Image:
    """Unit conversion + per-pixel wind speed, server side."""
    k = img.select(["temperature_2m", "temperature_2m_max", "temperature_2m_min",
                    "dewpoint_temperature_2m"]).subtract(273.15).rename(
        ["t2m_c", "t2m_max_c", "t2m_min_c", "dewpoint_c"])
    pr = img.select("total_precipitation_sum").multiply(1000).rename("precip_era5_mm")
    sw = img.select(["volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2"]).rename(
        ["swvl1_m3m3", "swvl2_m3m3"])
    rad = img.select("surface_solar_radiation_downwards_sum").divide(1e6).rename("ssrd_mjm2")
    u = img.select("u_component_of_wind_10m")
    v = img.select("v_component_of_wind_10m")
    ws = u.hypot(v).rename("wind10m_ms")
    return k.addBands([pr, sw, rad, ws, u.rename("u10_ms"), v.rename("v10_ms")])


RENAME = {
    "gpm": {"precipitation": "precip_gpm_mm"},
    "gldas": {"RootMoist_inst": "gldas_rootmoist_kgm2", "SoilMoi0_10cm_inst": "gldas_sm0_10_kgm2"},
    "smap": {"sm_surface": "smap_sm_surface_m3m3", "sm_rootzone": "smap_sm_rootzone_m3m3"},
}


def _fc_for_range(ds: str, geom: ee.Geometry, mask: ee.Image, start: date, end: date
                  ) -> ee.FeatureCollection:
    """Server-side FeatureCollection of daily area means for [start, end)."""
    spec = DATASETS[ds]
    col = ee.ImageCollection(spec["collection"]).select(spec["bands"])
    scale = spec["scale"]
    reducer = ee.Reducer.mean()

    def reduce(img, d0):
        vals = img.updateMask(mask).reduceRegion(reducer, geom, scale, bestEffort=True,
                                                 maxPixels=1e9, tileScale=2)
        return ee.Feature(None, vals).set("date", d0.format("YYYY-MM-dd"))

    if spec["kind"] == "daily":
        col = col.filterDate(start.isoformat(), end.isoformat())
        return col.map(lambda img: reduce(_era5_prep(img), img.date()))

    s = ee.Date(start.isoformat())
    n = (end - start).days
    days = ee.List.sequence(0, n - 1)
    col = col.filterDate(start.isoformat(), end.isoformat())
    names = list(RENAME[ds].values())

    def per_day(i):
        d0 = s.advance(i, "day")
        sub = col.filterDate(d0, d0.advance(1, "day"))
        if spec["kind"] == "sum_halfhour":
            img = sub.sum().multiply(0.5)  # mm/h x 0.5 h per half-hour image
        else:
            img = sub.mean()
        img = ee.Image(ee.Algorithms.If(sub.size().gt(0), img.rename(names),
                                        ee.Image.constant([0] * len(names)).rename(names)
                                        .updateMask(0)))
        return reduce(img, d0).set("n_images", sub.size())

    return ee.FeatureCollection(days.map(per_day))


def _getinfo_rows(ds, geom, mask, start, end):
    fc = _fc_for_range(ds, geom, mask, start, end)
    feats = fc.getInfo()["features"]
    return [f["properties"] for f in feats]


TRANSIENT = ("timed out", "Too many concurrent", "rate", "quota", "503", "502", "500",
             "Internal error", "Deadline", "Connection", "temporarily", "unavailable")
HEAVY = ("memory limit", "timed out", "Computation timed out", "too large", "Too many")


def _with_retry(fn, label, tries=6):
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - GEE raises many types
            msg = str(e)
            if attempt == tries:
                raise
            wait = min(120, 2 ** attempt + random.random() * 3)
            log.warning("%s attempt %d failed (%s); retry in %.0fs", label, attempt, msg[:160], wait)
            time.sleep(wait)


def _year_range(ds: str, year: int) -> tuple[date, date] | None:
    first = DATASETS[ds]["first"]
    start = max(date(year, 1, 1), first)
    end = date(year + 1, 1, 1)
    today = date.today()
    end = min(end, today)
    if start >= end:
        return None
    return start, end


def chunk_path(ds: str, area: str, year: int):
    return RAW_DIR / ds / f"{areas_mod.slug(area)}_{year}.parquet"


def fetch_chunk(ds: str, area: str, geom, mask, year: int) -> str:
    path = chunk_path(ds, area, year)
    if path.exists():
        return "cached"
    rng = _year_range(ds, year)
    if rng is None:
        return "out_of_range"
    start, end = rng
    label = f"{ds}/{area}/{year}"
    t0 = time.time()
    try:
        rows = _with_retry(lambda: _getinfo_rows(ds, geom, mask, start, end), label, tries=4)
    except Exception as e:  # noqa: BLE001
        log.warning("%s full-year failed (%s); splitting by month", label, str(e)[:160])
        rows = []
        for m in range(start.month, 13):
            ms = max(date(year, m, 1), start)
            me = min(date(year + (m == 12), m % 12 + 1, 1), end)
            if ms >= me:
                continue
            rows += _with_retry(lambda ms=ms, me=me: _getinfo_rows(ds, geom, mask, ms, me),
                                f"{label}/{m:02d}", tries=6)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]")})
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns=RENAME.get(ds, {}))
    df.insert(1, "area_name", area)
    df = df.sort_values("date").drop_duplicates("date")
    for c in df.columns:
        if c not in ("date", "area_name"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    log.info("%s: %d rows in %.1fs", label, len(df), time.time() - t0)
    return "done"


def run(datasets, area_names, start_year, end_year, workers=8):
    areas_mod.init()
    all_areas = areas_mod.get_areas()
    if area_names:
        missing = [a for a in area_names if a not in all_areas]
        if missing:
            raise KeyError(f"Unknown areas {missing}; available {list(all_areas)}")
        all_areas = {k: v for k, v in all_areas.items() if k in area_names}
    for ds in [d for d in PRIORITY if d in datasets]:
        tasks = [(ds, a, g, m, y) for y in range(start_year, end_year + 1)
                 for a, (g, m) in all_areas.items()
                 if _year_range(ds, y) and not chunk_path(ds, a, y).exists()]
        log.info("== %s: %d chunks to fetch", ds, len(tasks))
        t0 = time.time()
        failed = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch_chunk, *t): t for t in tasks}
            for i, f in enumerate(as_completed(futs), 1):
                t = futs[f]
                try:
                    f.result()
                except Exception as e:  # noqa: BLE001
                    failed.append((t[0], t[1], t[4]))
                    log.error("FAILED %s/%s/%s: %s", t[0], t[1], t[4], str(e)[:300])
                if i % 20 == 0 or i == len(tasks):
                    log.info("%s progress %d/%d (%.0f s elapsed)", ds, i, len(tasks),
                             time.time() - t0)
        log.info("== %s finished in %.0f s; %d failed: %s", ds, time.time() - t0, len(failed),
                 failed)


def _rh(t, td):
    """Relative humidity (%) from T and Td in °C (Magnus)."""
    a, b = 17.625, 243.04
    return 100 * np.exp(a * td / (b + td) - a * t / (b + t))


def combine(start_year=config.YEAR_START, end_year=config.YEAR_END) -> pd.DataFrame:
    frames = {}
    for ds in PRIORITY:
        files = sorted((RAW_DIR / ds).glob("*.parquet"))
        if not files:
            continue
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        df = df.drop(columns=[c for c in ("n_images",) if c in df.columns])
        frames[ds] = df
    if not frames:
        raise RuntimeError("No cached chunks found")
    keys = ["date", "area_name"]
    out = None
    for ds, df in frames.items():
        out = df if out is None else out.merge(df, on=keys, how="outer")
    out = out[(out["date"].dt.year >= start_year) & (out["date"].dt.year <= end_year)]
    if {"t2m_c", "dewpoint_c"} <= set(out.columns):
        out["rh_pct"] = _rh(out["t2m_c"], out["dewpoint_c"]).clip(upper=100)
    out = out.sort_values(keys).reset_index(drop=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    log.info("wrote %s: %d rows, %d cols", OUT_PATH, len(out), out.shape[1])
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--start-year", type=int, default=config.YEAR_START)
    p.add_argument("--end-year", type=int, default=config.YEAR_END)
    p.add_argument("--areas", default="", help="comma-separated GAUL names / 'national' (default all)")
    p.add_argument("--datasets", default=",".join(PRIORITY))
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--combine-only", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    if not a.combine_only:
        ds = [d.strip() for d in a.datasets.split(",") if d.strip()]
        areas = [x.strip() for x in a.areas.split(",") if x.strip()]
        run(ds, areas, a.start_year, min(a.end_year, date.today().year), min(a.workers, 8))
    combine(a.start_year, a.end_year)


if __name__ == "__main__":
    main()
