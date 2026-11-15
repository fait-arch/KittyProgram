"""Climatología de referencia WorldClim v1 (estaciones, 1960–1990) y metadatos por área.

Sirve para corregir el sesgo frío de ERA5-Land en la Costa (método delta mensual)
y para dar latitud/altitud media a la fórmula de ET0.

    ml/.venv/bin/python -m ml.etl.worldclim
"""
import sys

import ee
import pandas as pd

from ml.config import DATA_PROCESSED, ROOT

sys.path.insert(0, str(ROOT.parent / "BACK"))
from nasa_data import init_gee  # noqa: E402

from ml.etl.areas import get_areas  # noqa: E402


def main():
    init_gee()
    wc = ee.ImageCollection("WORLDCLIM/V1/MONTHLY")
    srtm = ee.Image("USGS/SRTMGL1_003")
    clim, meta = [], []
    for name, (geom, mask) in get_areas().items():
        def per_month(img, geom=geom, mask=mask):
            v = (img.select(["tavg", "tmin", "tmax"]).multiply(0.1)
                 .addBands(img.select("prec")).updateMask(mask)
                 .reduceRegion(ee.Reducer.mean(), geom, 1000, bestEffort=True, maxPixels=1e9))
            return ee.Feature(None, v).set("month", img.get("month"))
        for f in wc.map(per_month).getInfo()["features"]:
            clim.append({"area_name": name, **f["properties"]})
        stats = (srtm.addBands(ee.Image.pixelLonLat()).updateMask(mask)
                 .reduceRegion(ee.Reducer.mean(), geom, 1000, bestEffort=True, maxPixels=1e9).getInfo())
        meta.append({"area_name": name, "lat": stats["latitude"], "lon": stats["longitude"],
                     "elev_m": stats["elevation"]})
    clim = pd.DataFrame(clim).rename(columns={"tavg": "wc_tavg_c", "tmin": "wc_tmin_c",
                                              "tmax": "wc_tmax_c", "prec": "wc_prec_mm"})
    clim["month"] = clim["month"].astype(int)
    clim = clim.sort_values(["area_name", "month"]).reset_index(drop=True)
    meta = pd.DataFrame(meta)
    clim.to_parquet(DATA_PROCESSED / "worldclim_monthly.parquet", index=False)
    meta.to_parquet(DATA_PROCESSED / "area_meta.parquet", index=False)
    print(meta.round(2).to_string(index=False))
    print(clim.groupby("area_name").agg(tavg=("wc_tavg_c", "mean"), prec=("wc_prec_mm", "sum")).round(1))


if __name__ == "__main__":
    main()
