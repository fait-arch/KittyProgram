# 7. Extracción de datos (fuentes y código)

Fuentes elegidas de la lista oficial del reto *Field Shift* que **cubren Ecuador**.
Se descartan las que solo cubren EE. UU. (SSURGO, CDL, PRISM, NAIP, NLCD, NLDAS, NASS, OpenET…).

## Fuentes seleccionadas

| # | Fuente | Origen | Qué aporta | Resolución | Acceso |
|---|--------|--------|------------|------------|--------|
| 1 | **GPM IMERG** | NASA | Lluvia mensual, aguaceros | ~11 km | GEE |
| 2 | **SMAP L4** | NASA | Humedad del suelo superficie / raíces (2015→) | ~11 km | GEE |
| 3 | **GLDAS 2.1** | NASA | Humedad del suelo y ET (2000→), serie larga | ~25 km | GEE |
| 4 | **MODIS** | NASA | NDVI, LST, ET real (2000→) | 250 m–1 km | GEE |
| 5 | **HLS** (Landsat + Sentinel-2) | NASA | NDVI a nivel de finca | 30 m | GEE |
| 6 | **SRTM** | NASA | Altitud, pendiente | 30 m | GEE |
| 7 | **ECOSTRESS** | NASA | LST, ET diaria, índice de estrés (ESI) | 70 m | AppEEARS |
| 8 | **NASA POWER** | NASA | Clima diario por punto (sin cuenta) | ~55 km | API REST |
| 9 | **ERA5-Land** | ESA/ECMWF (socio del reto) | Clima diario a ~9 km: temperatura, punto de rocío, viento, radiación, lluvia, humedad del suelo en 4 capas | ~9 km | GEE |
| 10 | **NEX-GDDP-CMIP6** | NASA | **Proyecciones de cambio climático** 1950–2100 (SSP2-4.5 / SSP5-8.5) | ~25 km | GEE |
| + | SoilGrids/OpenLandMap · ESA WorldCover · FAO GAEZ | ISRIC · ESA · FAO | Suelo · cobertura · aptitud de cultivos | 10–250 m | GEE / descarga |

### ¿Cuál usar para cada variable?

| Variable | Principal | Respaldo / validación |
|----------|-----------|-----------------------|
| Lluvia | GPM IMERG | ERA5-Land |
| Temperatura (media, máx, mín) | **ERA5-Land** | NASA POWER |
| ET₀ (demanda de agua) | **FAO-56 con ERA5-Land** | FAO-56 con POWER |
| ET real | MODIS MOD16 | ECOSTRESS, GLDAS |
| Humedad del suelo | SMAP (2015→) | GLDAS / ERA5-Land (2000→) |
| Heladas | ERA5-Land `temperature_2m_min` | POWER `T2M_MIN` |
| Vegetación / suelo desnudo | MODIS NDVI (historia) | HLS (finca) |
| Erosión | SRTM + GPM | — |
| Estrés térmico/hídrico en finca | ECOSTRESS | MODIS LST |
| Escenarios futuros | **NEX-GDDP-CMIP6** | — |

> **Por qué ERA5-Land para temperatura y no POWER:** POWER usa celdas de ~55 km. En Babahoyo
> asume 837 m de altitud (la real es ~12 m) y da una T mínima de agosto ~15.5 °C cuando la real
> ronda 21–22 °C. ERA5-Land (~9 km) representa mucho mejor la Costa. POWER se mantiene como
> referencia NASA citada.

---

## Método 1 · Google Earth Engine

### Función genérica: climatología mensual

```python
import ee

def monthly_climatology(col_id, band, geom, start="2005-01-01", end="2025-12-31",
                        scale=5000, transform=None, reducer=None):
    """Valor medio de cada mes (1–12) sobre el área. Una sola llamada a getInfo()."""
    col = ee.ImageCollection(col_id).filterDate(start, end).select(band)
    if transform:
        col = col.map(transform)
    reducer = reducer or ee.Reducer.mean()

    def per_month(m):
        img = col.filter(ee.Filter.calendarRange(m, m, "month")).mean()
        v = img.reduceRegion(reducer, geom, scale, bestEffort=True, maxPixels=1e9).get(band)
        return ee.Feature(None, {"month": m, "value": v})

    fc = ee.FeatureCollection(ee.List.sequence(1, 12).map(per_month))
    return {f["properties"]["month"]: f["properties"]["value"]
            for f in fc.getInfo()["features"]}

def keep_time(fn):
    """Envuelve una transformación conservando la fecha de la imagen."""
    return lambda img: fn(img).copyProperties(img, ["system:time_start"])
```

### Parámetros por fuente

| Variable | `col_id` | `band` | Conversión |
|----------|----------|--------|------------|
| Lluvia | `NASA/GPM_L3/IMERG_MONTHLY_V07` | `precipitation` | mm/h × 24 × días del mes |
| Humedad superficial | `NASA/SMAP/SPL4SMGP/008` | `sm_surface` | m³/m³ (usar 2016→) |
| Humedad raíces | `NASA/SMAP/SPL4SMGP/008` | `sm_rootzone` | m³/m³ |
| Humedad raíces (larga) | `NASA/GLDAS/V021/NOAH/G025/T3H` | `RootMoist_inst` | kg/m² |
| NDVI | `MODIS/061/MOD13Q1` | `NDVI` | × 0.0001 |
| LST día | `MODIS/061/MOD11A2` | `LST_Day_1km` | × 0.02 − 273.15 → °C |
| ET real | `MODIS/061/MOD16A2GF` | `ET` | × 0.1 → mm / 8 días |
| Temperatura media | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | `temperature_2m` | − 273.15 → °C |
| Lluvia (ERA5) | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | `total_precipitation_sum` | × 1000 → mm/mes |
| Humedad suelo (ERA5) | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | `volumetric_soil_water_layer_1` … `_4` | m³/m³ (capas 0–7, 7–28, 28–100, 100–289 cm) |

### ERA5-Land diario → ET₀ FAO-56 y heladas

`ECMWF/ERA5_LAND/DAILY_AGGR` tiene todo lo necesario para Penman-Monteith:

| Banda | Unidad | Uso |
|-------|--------|-----|
| `temperature_2m_max`, `temperature_2m_min` | K | T máx/mín (− 273.15) |
| `dewpoint_temperature_2m` | K | Presión de vapor real → humedad |
| `u_component_of_wind_10m`, `v_component_of_wind_10m` | m/s | Viento a 10 m → convertir a 2 m (× 0.748) |
| `surface_solar_radiation_downwards_sum` | J/m²/día | ÷ 10⁶ → MJ/m²/día |
| `total_precipitation_sum` | m | × 1000 → mm |

> No usar `potential_evaporation_sum` como ET₀: es evaporación de superficie de agua libre y
> sobreestima la demanda del cultivo.

```python
def era5_daily_table(geom, start, end, scale=9000):
    """Serie diaria promedio sobre el área (para ET₀ y días de helada)."""
    bands = ["temperature_2m_max", "temperature_2m_min", "dewpoint_temperature_2m",
             "u_component_of_wind_10m", "v_component_of_wind_10m",
             "surface_solar_radiation_downwards_sum", "total_precipitation_sum"]
    col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start, end).select(bands)

    def to_feat(img):
        vals = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True)
        return ee.Feature(None, vals).set("date", img.date().format("YYYY-MM-dd"))

    # Pedir por años (≈365 filas por llamada) para no exceder límites de GEE
    return [f["properties"] for f in col.map(to_feat).getInfo()["features"]]
```

```python
import math

def et0_fao56(tmax_c, tmin_c, tdew_c, u2, rs_mj, elev_m, lat_deg, doy):
    """ET₀ diaria (mm) — FAO-56 Penman-Monteith."""
    tmean = (tmax_c + tmin_c) / 2
    p = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26
    gamma = 0.000665 * p
    es = lambda t: 0.6108 * math.exp(17.27 * t / (t + 237.3))
    e_s = (es(tmax_c) + es(tmin_c)) / 2
    e_a = es(tdew_c)
    delta = 4098 * es(tmean) / (tmean + 237.3) ** 2
    # radiación neta
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    dec = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(-math.tan(phi) * math.tan(dec))
    ra = 24 * 60 / math.pi * 0.082 * dr * (ws * math.sin(phi) * math.sin(dec)
                                           + math.cos(phi) * math.cos(dec) * math.sin(ws))
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = 0.77 * rs_mj
    sigma = 4.903e-9
    rnl = sigma * (((tmax_c + 273.16) ** 4 + (tmin_c + 273.16) ** 4) / 2) \
          * (0.34 - 0.14 * math.sqrt(e_a)) * (1.35 * min(rs_mj / rso, 1.0) - 0.35)
    rn = rns - rnl
    return (0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (e_s - e_a)) \
           / (delta + gamma * (1 + 0.34 * u2))

# Por cada fila de era5_daily_table:
#   tmax = r["temperature_2m_max"] - 273.15 ; tmin = ... ; tdew = ...
#   u10  = hypot(r["u_component_of_wind_10m"], r["v_component_of_wind_10m"]); u2 = u10 * 0.748
#   rs   = r["surface_solar_radiation_downwards_sum"] / 1e6
#   frost = tmin < 2
```

### NEX-GDDP-CMIP6 → escenarios de cambio climático

Colección `NASA/GDDP-CMIP6`, diaria, propiedades `model` y `scenario`
(`historical`, `ssp245`, `ssp585`). Bandas: `tas`, `tasmax`, `tasmin` (K),
`pr` (kg m⁻² s⁻¹ → × 86400 = mm/día), `hurs` (%), `sfcWind` (m/s), `rsds` (W/m²).

```python
MODELS = ["ACCESS-CM2", "EC-Earth3", "GFDL-ESM4", "MRI-ESM2-0"]   # ensamble pequeño

def cmip6_monthly(geom, scenario, start, end, band, transform):
    out = {}
    for m in MODELS:
        col = (ee.ImageCollection("NASA/GDDP-CMIP6")
               .filter(ee.Filter.eq("model", m))
               .filter(ee.Filter.eq("scenario", scenario)))
        out[m] = monthly_climatology_from(col, band, geom, start, end, transform)
    return out

def monthly_climatology_from(col, band, geom, start, end, transform, scale=25000):
    col = col.filterDate(start, end).select(band).map(keep_time(transform))
    def per_month(mo):
        img = col.filter(ee.Filter.calendarRange(mo, mo, "month")).mean()
        v = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True).get(band)
        return ee.Feature(None, {"month": mo, "value": v})
    fc = ee.FeatureCollection(ee.List.sequence(1, 12).map(per_month)).getInfo()
    return {f["properties"]["month"]: f["properties"]["value"] for f in fc["features"]}

# Cambio esperado = futuro − histórico, por modelo y mes:
base   = cmip6_monthly(canton, "historical", "1995-01-01", "2014-12-31", "pr", lambda i: i.multiply(86400))
future = cmip6_monthly(canton, "ssp245",     "2041-01-01", "2060-12-31", "pr", lambda i: i.multiply(86400))
# delta_pct[m][mes] = (future - base) / base * 100   → alimenta el simulador de escenarios
```

Mostrar **el rango entre modelos** (mín–máx) como incertidumbre, no un único número.

### Datos estáticos

```python
dem   = ee.Image("USGS/SRTMGL1_003")
slope = ee.Terrain.slope(dem)
terrain = ee.Image.cat(dem.rename("elev"), slope.rename("slope")).reduceRegion(
    ee.Reducer.mean().combine(ee.Reducer.percentile([90]), sharedInputs=True),
    geom, 90, bestEffort=True).getInfo()

soil = ee.Image.cat(
    ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02").select("b0").rename("ph_x10"),
    ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M_v02").select("b0").rename("soc"),
    ee.Image("OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02").select("b0").rename("clay"),
    ee.Image("OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02").select("b0").rename("sand"),
).reduceRegion(ee.Reducer.mean(), geom, 250, bestEffort=True).getInfo()
# Revisar en la ficha de cada capa su factor de escala.

cover = ee.Image("ESA/WorldCover/v200").first().reduceRegion(
    ee.Reducer.frequencyHistogram(), geom, 10, bestEffort=True).getInfo()
```

### HLS: NDVI de la finca a 30 m

```python
def hls_ndvi(geom, start, end):
    cloudfree = lambda img: img.updateMask(img.select("Fmask").bitwiseAnd(1 << 1).eq(0))
    l30 = (ee.ImageCollection("NASA/HLS/HLSL30/v002").filterBounds(geom).filterDate(start, end)
           .map(cloudfree).map(keep_time(lambda i: i.normalizedDifference(["B5", "B4"]).rename("NDVI"))))
    s30 = (ee.ImageCollection("NASA/HLS/HLSS30/v002").filterBounds(geom).filterDate(start, end)
           .map(cloudfree).map(keep_time(lambda i: i.normalizedDifference(["B8A", "B4"]).rename("NDVI"))))
    return l30.merge(s30)
```

---

## Método 2 · NASA POWER (API REST, sin cuenta)

```python
import httpx

POWER = "https://power.larc.nasa.gov/api/temporal"
PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"

def power_climatology(lat, lon):
    r = httpx.get(f"{POWER}/climatology/point", timeout=30, params={
        "parameters": PARAMS, "community": "AG",
        "latitude": lat, "longitude": lon, "format": "JSON"})
    r.raise_for_status()
    return r.json()["properties"]["parameter"]   # {"T2M": {"JAN": 23.0, …, "ANN": 23.2}}

def power_monthly(lat, lon, start_year=2005, end_year=2024):
    r = httpx.get(f"{POWER}/monthly/point", timeout=60, params={
        "parameters": PARAMS, "community": "AG", "latitude": lat, "longitude": lon,
        "start": start_year, "end": end_year, "format": "JSON"})
    r.raise_for_status()
    return r.json()["properties"]["parameter"]   # {"T2M": {"202001": 23.4, …}}
```

No usar `EVPTRNS` como ET₀: es evapotranspiración real del modelo.

---

## Método 3 · AppEEARS (ECOSTRESS)

Requiere cuenta Earthdata. Las tareas tardan de minutos a horas: pedir una vez y guardar.

```python
import os, httpx

API = "https://appeears.earthdatacloud.nasa.gov/api"

tok = httpx.post(f"{API}/login",
                 auth=(os.environ["EARTHDATA_USER"], os.environ["EARTHDATA_PASS"])).json()["token"]
H = {"Authorization": f"Bearer {tok}"}

task = {
  "task_type": "area", "task_name": "finca-<id>",
  "params": {
    "dates": [{"startDate": "01-01-2023", "endDate": "12-31-2024"}],
    "layers": [
      {"product": "ECO_L2T_LSTE.002", "layer": "LST"},
      {"product": "ECO_L3T_JET.002",  "layer": "ETdaily"},
      {"product": "ECO_L4T_ESI.002",  "layer": "ESI"}
    ],
    "output": {"format": {"type": "geotiff"}, "projection": "geographic"},
    "geo": {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": FINCA_GEOJSON}]}
  }
}
task_id = httpx.post(f"{API}/task", json=task, headers=H).json()["task_id"]
status  = httpx.get(f"{API}/task/{task_id}", headers=H).json()["status"]   # "done"
files   = httpx.get(f"{API}/bundle/{task_id}", headers=H).json()["files"]
# Descargar: GET {API}/bundle/{task_id}/{file_id} → GeoTIFF → resumir con rasterio
```

Variables nuevas en `.env`: `EARTHDATA_USER`, `EARTHDATA_PASS`.

---

## Método 4 · FAO GAEZ v4 (descarga manual)

1. https://gaez.fao.org → *Data Viewer* → *Suitability and Attainable Yield* → cultivo → GeoTIFF.
2. Subir a GEE como asset y leer con `ee.Image("projects/<proyecto>/assets/gaez_<cultivo>")`,
   o resumir por cantón con `rasterio` y guardar en Supabase.
3. Usar como "segunda opinión" en la evidencia de cada estrategia.

---

## Orden de implementación

1. **ERA5-Land diario + FAO-56** → temperatura, ET₀, heladas (corrige el sesgo de POWER en la Costa).
2. **GPM, MODIS NDVI, SRTM** → lluvia, suelo desnudo, erosión.
3. **SMAP / GLDAS, HLS** → humedad del suelo y detalle de finca.
4. **NEX-GDDP-CMIP6** → simulador de escenarios futuros.
5. **ECOSTRESS** → capa visual de estrés (si sobra tiempo).

Todo resultado se guarda en Supabase (`area_climatology`, `area_monthly_series`,
`area_static_features`) — ver [Caché de datos NASA](06-cache-nasa.md).

## Atribución obligatoria en la app

- NASA: GPM IMERG, SMAP, GLDAS, MODIS, HLS, SRTM, ECOSTRESS, POWER, NEX-GDDP-CMIP6.
- "Contains modified Copernicus Climate Change Service information" (ERA5-Land).
- ISRIC SoilGrids / OpenLandMap (CC BY 4.0) · ESA WorldCover (CC BY 4.0) · FAO GAEZ.
