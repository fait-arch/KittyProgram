"""Aptitud del cacao FAO GAEZ v4 por área (hoy y 2050) — capa complementaria al modelo.

GAEZ v4, tema 4 "Suitability and Attainable Yield", índice de aptitud del cacao (`su*r_coc`,
secano), 5 arcmin, 0–10 000:
    histórico 1981–2010 (CRU TS 3.2), manejo alto (H) y bajo (L)
    2050s (2041–2070), ensamble de modelos climáticos, RCP4.5 y RCP8.5, manejo alto
Fuente: https://gaez.fao.org (rasters en s3 data.gaezdev.aws.fao.org/res05/…).

Se promedia el índice dentro del polígono de cada área (país, provincias y los 125 cantones, mismos
polígonos de Earth Engine que el resto del modelo). No entra al modelo de pérdida: es un mapa fijo
(promedio de 30 años) y el modelo predice anomalías de cada año.

    ml/.venv/bin/python -m ml.etl.gaez      → data/processed/gaez_suitability.parquet
"""
from __future__ import annotations

import urllib.request

import ee
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
from shapely.geometry import shape

from .. import config
from . import areas as A
from .cantons import _geom

BASE = "https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/res05"
LAYERS = {
    "si_hoy_alto": "CRUTS32/Hist/8110H/suHr_coc.tif",
    "si_hoy_bajo": "CRUTS32/Hist/8110L/suLr_coc.tif",
    "si_2050_rcp45_alto": "ENSEMBLE/rcp4p5/2050sH/suHr_coc.tif",
    "si_2050_rcp85_alto": "ENSEMBLE/rcp8p5/2050sH/suHr_coc.tif",
}
RAW = config.DATA_RAW / "gaez"
OUT = config.DATA_PROCESSED / "gaez_suitability.parquet"
# Clases GAEZ del índice de aptitud (0–10 000)
CLASSES = [(8500, "muy_alta"), (7000, "alta"), (5500, "buena"), (4000, "media"), (2500, "moderada"),
           (1000, "marginal"), (1, "muy_marginal"), (-1, "no_apta")]


def suit_class(v: float) -> str:
    return next(name for lim, name in CLASSES if v >= lim) if pd.notna(v) else None


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    for key, rel in LAYERS.items():
        f = RAW / rel.replace("/", "_")
        if not f.exists():
            urllib.request.urlretrieve(f"{BASE}/{rel}", f)


def polygons() -> dict:
    """{area_name: shapely geometry} desde Earth Engine (país, provincias, cantones)."""
    A.init()
    out = {n: g for n, (g, _) in A.get_areas().items()}
    g = pd.read_csv(config.DATA_PROCESSED / "canton_gaul_match.csv", dtype=str).dropna(subset=["gaul_code"])
    out.update({r.id: _geom(r.gaul_code) for r in g.itertuples()})
    fc = ee.FeatureCollection([ee.Feature(geom.simplify(1000), {"area_name": n}) for n, geom in out.items()])
    feats = fc.getInfo()["features"]
    return {f["properties"]["area_name"]: shape(f["geometry"]) for f in feats}


def zonal(polys: dict) -> pd.DataFrame:
    rows = {n: {"area_name": n} for n in polys}
    for key, rel in LAYERS.items():
        with rasterio.open(RAW / rel.replace("/", "_")) as src:
            for n, geom in polys.items():
                try:
                    arr, _ = rasterio.mask.mask(src, [geom], crop=True, all_touched=True, filled=False)
                    v = arr.compressed()
                    v = v[(v >= 0) & (v <= 10000)]
                    rows[n][key] = float(v.mean()) if v.size else np.nan
                except ValueError:
                    rows[n][key] = np.nan
    df = pd.DataFrame(rows.values())
    for k in LAYERS:
        df[k.replace("si_", "clase_")] = df[k].map(suit_class)
    df["cambio_2050_rcp45_pct"] = 100 * (df.si_2050_rcp45_alto / df.si_hoy_alto - 1)
    df["cambio_2050_rcp85_pct"] = 100 * (df.si_2050_rcp85_alto / df.si_hoy_alto - 1)
    return df


def main():
    download()
    df = zonal(polygons())
    df.to_parquet(OUT, index=False)
    print(f"{OUT}: {len(df)} áreas")
    print(df[df.area_name.isin(["national", "Los Rios", "Guayas", "Manabi", "Esmeraldas", "El Oro",
                                "Santo Domingo de los Tsachilas", "Sucumbios"])]
          [["area_name", "si_hoy_alto", "si_2050_rcp45_alto", "si_2050_rcp85_alto", "cambio_2050_rcp85_pct",
            "clase_hoy_alto", "clase_2050_rcp85_alto"]].round(0).to_string(index=False))


if __name__ == "__main__":
    main()
