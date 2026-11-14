"""Fuentes 3–8 y 15 — Google Earth Engine (IDs verificados en APIS-DATOS.md).

Requiere: GEE_PROJECT en .env + `earthengine authenticate`.
Destinos: `areas`, `area_monthly_series`, `area_static_features`, `area_scenario_climate`.
"""
import calendar

from app.core.gee import require_gee

# ── IDs del catálogo (docs/APIS-DATOS.md) ──
ERA5_DAILY = "ECMWF/ERA5_LAND/DAILY_AGGR"
GPM_MONTHLY = "NASA/GPM_L3/IMERG_MONTHLY_V07"
GPM_30MIN = "NASA/GPM_L3/IMERG_V07"
SMAP_L4 = "NASA/SMAP/SPL4SMGP/008"
GLDAS = "NASA/GLDAS/V021/NOAH/G025/T3H"
MODIS_NDVI = "MODIS/061/MOD13Q1"
SRTM = "USGS/SRTMGL1_003"
SOIL_PH = "OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02"
SOIL_OC = "OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M_v02"
WORLDCOVER = "ESA/WorldCover/v200"
GAUL_L1, GAUL_L2 = "FAO/GAUL/2015/level1", "FAO/GAUL/2015/level2"
CMIP6 = "NASA/GDDP-CMIP6"
CMIP6_MODELS = ["ACCESS-CM2", "EC-Earth3", "GFDL-ESM4", "MRI-ESM2-0"]


def _ee():
    require_gee()
    import ee
    return ee


# ── Geometrías ─────────────────────────────────────────────────────────
def point_area(lat: float, lon: float, radius_m: int = 5000):
    ee = _ee()
    return ee.Geometry.Point([lon, lat]).buffer(radius_m)


def cantons(provinces: list[str]):
    """FeatureCollection de cantones (GAUL level2) de Ecuador. GAUL va sin tildes: 'Los Rios'."""
    ee = _ee()
    return (ee.FeatureCollection(GAUL_L2)
            .filter(ee.Filter.eq("ADM0_NAME", "Ecuador"))
            .filter(ee.Filter.inList("ADM1_NAME", provinces)))


def canton_list(provinces: list[str]) -> list[dict]:
    fc = cantons(provinces).select(["ADM1_NAME", "ADM2_NAME", "ADM2_CODE"], None, False)
    return [f["properties"] for f in fc.getInfo()["features"]]


def canton_geom(province: str, canton: str):
    ee = _ee()
    return cantons([province]).filter(ee.Filter.eq("ADM2_NAME", canton)).geometry()


# ── Series diarias (para días favorables a enfermedades) ───────────────
def era5_daily(geom, start: str, end: str, scale: int = 9000) -> list[dict]:
    """Pedir año por año (≈ 365 filas). Convierte K→°C y m→mm."""
    ee = _ee()
    bands = ["temperature_2m", "temperature_2m_max", "temperature_2m_min",
             "dewpoint_temperature_2m", "total_precipitation_sum", "volumetric_soil_water_layer_1"]
    col = ee.ImageCollection(ERA5_DAILY).filterDate(start, end).select(bands)

    def to_feat(img):
        v = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True)
        return ee.Feature(None, v).set("date", img.date().format("YYYY-MM-dd"))

    rows = [f["properties"] for f in col.map(to_feat).getInfo()["features"]]
    for r in rows:
        for k in ("temperature_2m", "temperature_2m_max", "temperature_2m_min", "dewpoint_temperature_2m"):
            if r.get(k) is not None:
                r[k] = round(r[k] - 273.15, 2)
        if r.get("total_precipitation_sum") is not None:
            r["total_precipitation_sum"] = round(r["total_precipitation_sum"] * 1000, 2)
    return rows


def gpm_daily(geom, start: str, end: str, scale: int = 11000) -> list[dict]:
    """Lluvia diaria GPM IMERG (para contar días > 50 mm)."""
    ee = _ee()
    col = ee.ImageCollection(GPM_30MIN).filterDate(start, end).select("precipitation")
    n = ee.Date(end).difference(ee.Date(start), "day").subtract(1)
    days = ee.List.sequence(0, n)

    def per_day(d):
        d0 = ee.Date(start).advance(d, "day")
        img = col.filterDate(d0, d0.advance(1, "day")).sum().multiply(0.5)  # mm/h × 0.5 h
        v = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True).get("precipitation")
        return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "precip_mm": v})

    return [f["properties"] for f in ee.FeatureCollection(days.map(per_day)).getInfo()["features"]]


# ── Serie mensual de un año ────────────────────────────────────────────
def _monthly_mean(collection_id: str, band: str, geom, year: int, scale: int) -> list:
    ee = _ee()
    col = ee.ImageCollection(collection_id).select(band)

    def per_month(m):
        s = ee.Date.fromYMD(year, m, 1)
        sub = col.filterDate(s, s.advance(1, "month"))
        val = ee.Algorithms.If(
            sub.size().gt(0),
            sub.mean().reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True).get(band),
            None)
        return ee.Feature(None, {"month": m, "value": val})

    fc = ee.FeatureCollection(ee.List.sequence(1, 12).map(per_month)).getInfo()
    return [f["properties"].get("value") for f in sorted(fc["features"], key=lambda f: f["properties"]["month"])]


def monthly_series(geom, year: int) -> list[dict]:
    """12 filas con NDVI (MODIS), lluvia (GPM mensual) y humedad de suelo (SMAP desde 2015)."""
    ndvi = _monthly_mean(MODIS_NDVI, "NDVI", geom, year, 250)
    gpm = _monthly_mean(GPM_MONTHLY, "precipitation", geom, year, 11000)
    if year >= 2015:
        sm_s = _monthly_mean(SMAP_L4, "sm_surface", geom, year, 11000)
        sm_r = _monthly_mean(SMAP_L4, "sm_rootzone", geom, year, 11000)
    else:
        sm_s = sm_r = [None] * 12  # antes de 2015: usar GLDAS (kg/m², otra unidad)

    rows = []
    for i in range(12):
        days = calendar.monthrange(year, i + 1)[1]
        rows.append({
            "month_date": f"{year}-{i + 1:02d}-01",
            "ndvi": round(ndvi[i] * 0.0001, 4) if ndvi[i] is not None else None,
            "precip_mm": round(gpm[i] * 24 * days, 1) if gpm[i] is not None else None,
            "sm_surface": round(sm_s[i], 4) if sm_s[i] is not None else None,
            "sm_rootzone": round(sm_r[i], 4) if sm_r[i] is not None else None,
        })
    return rows


# ── Rasgos estáticos (suelo, relieve, cobertura) ───────────────────────
def static_features(geom) -> dict:
    ee = _ee()
    dem = ee.Image(SRTM).select("elevation")
    slope = ee.Terrain.slope(dem)
    ph = ee.Image(SOIL_PH).select("b0").divide(10)
    oc = ee.Image(SOIL_OC).select("b0")
    wc = ee.ImageCollection(WORLDCOVER).first().select("Map")
    img = ee.Image.cat([
        dem.rename("elevation_m"), slope.rename("slope_deg"), ph.rename("soil_ph"),
        oc.rename("soil_oc_raw"),
        wc.eq(40).rename("cropland_frac"), wc.eq(10).rename("tree_frac"),
    ])
    v = img.reduceRegion(ee.Reducer.mean(), geom, 100, bestEffort=True).getInfo()
    return {k: (round(val, 3) if isinstance(val, (int, float)) else val) for k, val in v.items()}


# ── Fase 2: NEX-GDDP-CMIP6 ─────────────────────────────────────────────
def cmip6_monthly(geom, scenario: str, start: str, end: str, band: str,
                  model: str = "ACCESS-CM2", scale: int = 25000) -> list[dict]:
    """Media mensual multianual (12 valores) de un modelo/escenario.
    Unidades crudas: tas en K (−273.15), pr en kg/m²/s (×86400 = mm/día)."""
    ee = _ee()
    col = (ee.ImageCollection(CMIP6).filter(ee.Filter.eq("model", model))
           .filter(ee.Filter.eq("scenario", scenario)).filterDate(start, end).select(band))

    def per_month(m):
        sub = col.filter(ee.Filter.calendarRange(m, m, "month"))
        v = sub.mean().reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True).get(band)
        return ee.Feature(None, {"month": m, "value": v})

    fc = ee.FeatureCollection(ee.List.sequence(1, 12).map(per_month)).getInfo()
    out = []
    for f in sorted(fc["features"], key=lambda f: f["properties"]["month"]):
        val = f["properties"].get("value")
        if val is not None:
            val = val - 273.15 if band.startswith("tas") else val * 86400 if band == "pr" else val
        out.append({"month": f["properties"]["month"], band: None if val is None else round(val, 3)})
    return out
