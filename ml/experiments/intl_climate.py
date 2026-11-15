"""Clima diario de las zonas cacaoteras de Colombia y Perú (GEE) para el experimento multi-país.

Zonas = unión de los departamentos/regiones con ~80 % de la producción de cacao, < 1200 m
(en esos países el cacao llega a 1200 m):
  Colombia: Santander, Antioquia, Arauca, Huila, Tolima, Nariño, Meta, Norte de Santander, Cesar
  Perú:     San Martín, Junín, Cusco, Ucayali, Huánuco, Ayacucho, Amazonas, Piura

Escribe data/processed/climate_daily_intl.parquet, worldclim_intl.parquet y area_meta_intl.parquet
(no toca los archivos de Ecuador).

    ml/.venv/bin/python -m ml.experiments.intl_climate
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import ee
import pandas as pd

from ml import config
from ml.etl import areas as A
from ml.etl import gee_daily as G

ZONES = {
    "colombia": ("Colombia", ["Santander", "Antioquia", "Arauca", "Huila", "Tolima", "Narino", "Meta",
                              "Norte De Santander", "Cesar"]),
    "peru": ("Peru", ["San Martín", "Junín", "Cusco", "Ucayali", "Huánuco", "Ayacucho", "Amazonas", "Piura"]),
}
RAW = config.DATA_RAW / "gee_intl"
YEARS = {"era5": (1961, 2025), "gpm": (1998, 2025), "modis": (2000, 2025)}
log = logging.getLogger("intl")


def zones():
    fc = ee.FeatureCollection("FAO/GAUL/2015/level1")
    mask = ee.Image(A.SRTM).select("elevation").lt(1200).selfMask().rename("cacao_land")
    out = {}
    for key, (country, adm1) in ZONES.items():
        g = fc.filter(ee.Filter.eq("ADM0_NAME", country)).filter(ee.Filter.inList("ADM1_NAME", adm1))
        out[key] = (g.geometry(maxError=500).simplify(2000), mask)
    return out


def worldclim_meta(z):
    wc = ee.ImageCollection("WORLDCLIM/V1/MONTHLY")
    clim, meta = [], []
    for name, (geom, mask) in z.items():
        def per_month(img, geom=geom, mask=mask):
            v = (img.select(["tavg", "tmin", "tmax"]).multiply(0.1).addBands(img.select("prec")).updateMask(mask)
                 .reduceRegion(ee.Reducer.mean(), geom, 5000, bestEffort=True, maxPixels=1e9))
            return ee.Feature(None, v).set("month", img.get("month"))
        for f in wc.map(per_month).getInfo()["features"]:
            clim.append({"area_name": name, **f["properties"]})
        s = (ee.Image(A.SRTM).addBands(ee.Image.pixelLonLat()).updateMask(mask)
             .reduceRegion(ee.Reducer.mean(), geom, 5000, bestEffort=True, maxPixels=1e9).getInfo())
        meta.append({"area_name": name, "lat": s["latitude"], "lon": s["longitude"], "elev_m": s["elevation"]})
    clim = pd.DataFrame(clim).rename(columns={"tavg": "wc_tavg_c", "tmin": "wc_tmin_c", "tmax": "wc_tmax_c",
                                              "prec": "wc_prec_mm"})
    clim["month"] = clim.month.astype(int)
    clim.to_parquet(config.DATA_PROCESSED / "worldclim_intl.parquet", index=False)
    pd.DataFrame(meta).to_parquet(config.DATA_PROCESSED / "area_meta_intl.parquet", index=False)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    A.init()
    z = zones()
    worldclim_meta(z)
    G.RAW_DIR = RAW
    for ds, (y0, y1) in YEARS.items():
        tasks = [(ds, n, g, m, y) for n, (g, m) in z.items() for y in range(y0, y1 + 1)
                 if not G.chunk_path(ds, n, y).exists()]
        with ThreadPoolExecutor(8) as ex:
            bad = sum(1 for f in as_completed([ex.submit(G.fetch_chunk, *t) for t in tasks]) if f.exception())
        log.info("%s: %d trozos, fallos %d", ds, len(tasks), bad)
    frames = []
    for ds in YEARS:
        df = pd.concat([pd.read_parquet(f) for f in sorted((RAW / ds).glob("*.parquet"))], ignore_index=True)
        frames.append(df.drop(columns=[c for c in ("n_images",) if c in df.columns]))
    out = frames[0]
    for df in frames[1:]:
        out = out.merge(df, on=["date", "area_name"], how="left")
    out["rh_pct"] = G._rh(out.t2m_c, out.dewpoint_c).clip(upper=100)
    out.sort_values(["area_name", "date"]).to_parquet(config.DATA_PROCESSED / "climate_daily_intl.parquet", index=False)
    log.info("escrito climate_daily_intl: %d filas", len(out))


if __name__ == "__main__":
    main()
