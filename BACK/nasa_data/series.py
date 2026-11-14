"""Series mensuales de variables NASA vía Google Earth Engine.

Los IDs de variable coinciden con la tabla `variables` de Supabase.
Todo se agrega en el servidor de GEE y se trae con un único getInfo() por variable.
"""
from dataclasses import dataclass
from typing import Callable

import ee
import pandas as pd

from .gee import init_gee


@dataclass(frozen=True)
class Var:
    collection: str
    band: str
    reducer: str                       # cómo agregar las imágenes dentro del mes: mean | sum
    scale: int                         # metros para reduceRegion
    convert: Callable[[ee.Image], ee.Image]
    unit: str


VARIABLES: dict[str, Var] = {
    # GPM da mm/h promedio del mes -> mm/mes
    "precip": Var("NASA/GPM_L3/IMERG_MONTHLY_V07", "precipitation", "mean", 10000,
                  lambda i: i.multiply(24 * 30.4), "mm/mes"),
    "soil_moisture_surf": Var("NASA/SMAP/SPL4SMGP/008", "sm_surface", "mean", 11000,
                              lambda i: i, "m³/m³"),
    "soil_moisture_root": Var("NASA/SMAP/SPL4SMGP/008", "sm_rootzone", "mean", 11000,
                              lambda i: i, "m³/m³"),
    "ndvi": Var("MODIS/061/MOD13Q1", "NDVI", "mean", 250,
                lambda i: i.multiply(0.0001), "índice"),
    "lst_day": Var("MODIS/061/MOD11A2", "LST_Day_1km", "mean", 1000,
                   lambda i: i.multiply(0.02).subtract(273.15), "°C"),
    # MOD16 da mm por 8 días (×0.1); la suma de compuestos del mes ≈ mm/mes
    "et_actual": Var("MODIS/061/MOD16A2GF", "ET", "sum", 500,
                     lambda i: i.multiply(0.1), "mm/mes"),
}


def _geometry(lon=None, lat=None, geojson=None) -> ee.Geometry:
    if geojson is not None:
        return ee.Geometry(geojson)
    if lon is None or lat is None:
        raise ValueError("Pasa lon/lat o un geojson")
    return ee.Geometry.Point(lon, lat)


def _one_variable(var_id: str, geom: ee.Geometry, start: str, end: str) -> list[dict]:
    v = VARIABLES[var_id]
    col = ee.ImageCollection(v.collection).filterDate(start, end).select(v.band)
    s, e = ee.Date(start), ee.Date(end)
    n_months = e.difference(s, "month").round()

    def per_month(k):
        d0 = s.advance(k, "month")
        sub = col.filterDate(d0, d0.advance(1, "month"))
        img = sub.sum() if v.reducer == "sum" else sub.mean()
        val = ee.Algorithms.If(
            sub.size().gt(0),
            v.convert(img.rename("v")).reduceRegion(
                ee.Reducer.mean(), geom, v.scale, bestEffort=True, maxPixels=1e9
            ).get("v"),
            None,
        )
        return ee.Feature(None, {"month_date": d0.format("YYYY-MM-01"), "value": val})

    feats = ee.FeatureCollection(ee.List.sequence(0, n_months.subtract(1)).map(per_month))
    return [f["properties"] for f in feats.getInfo()["features"]]


def monthly_series(
    lon: float | None = None,
    lat: float | None = None,
    start: str = "2020-01-01",
    end: str = "2025-01-01",
    variables: list[str] | None = None,
    geojson: dict | None = None,
) -> pd.DataFrame:
    """Devuelve un DataFrame ancho: month_date + una columna por variable.

    - Punto: monthly_series(lon=-79.53, lat=-1.80)
    - Polígono (cantón/finca): monthly_series(geojson={...geometry...})
    - `end` es exclusivo. SMAP empieza en 2015-04; el resto antes.
    """
    init_gee()
    geom = _geometry(lon, lat, geojson)
    out = None
    for var_id in variables or list(VARIABLES):
        df = pd.DataFrame(_one_variable(var_id, geom, start, end)).rename(columns={"value": var_id})
        out = df if out is None else out.merge(df, on="month_date", how="outer")
    out["month_date"] = pd.to_datetime(out["month_date"])
    return out.sort_values("month_date").reset_index(drop=True)
