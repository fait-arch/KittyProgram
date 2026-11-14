# APIs y fuentes de datos — CacaoResiliente

Referencia rápida para **sacar los datos**. Todo lo marcado ✅ fue probado el 2026-11-14.

| # | Fuente | Acceso | Cuenta | Fase | Tabla destino |
|---|--------|--------|--------|------|---------------|
| 1 | NOAA CPC — ONI | Texto plano HTTP | No | 1 | `enso_index` |
| 2 | NOAA CPC — Niño 1+2 | Texto plano HTTP | No | 1 | `enso_index` |
| 3 | ERA5-Land diario | Google Earth Engine | GEE | 1 | `area_monthly_series` |
| 4 | GPM IMERG | Google Earth Engine | GEE | 1 | `area_monthly_series` |
| 5 | SMAP L4 | Google Earth Engine | GEE | 1 | `area_monthly_series` |
| 6 | MODIS NDVI | Google Earth Engine | GEE | 1 | `area_monthly_series` |
| 7 | SRTM, OpenLandMap, WorldCover | Google Earth Engine | GEE | 1 | `area_static_features` |
| 8 | FAO GAUL (límites) | Google Earth Engine | GEE | 1 | `areas` |
| 9 | ECOCROP | CSV en GitHub | No | 1 | `crop_requirements` |
| 10 | ESPAC (INEC) | Descarga XLSX/CSV | No | 1 | `crop_production_stats` |
| 11 | FAOSTAT | Descarga ZIP (bulk) | No | 1 | `crop_production_stats` |
| 12 | SIPA (MAG) | Descarga manual | No | 1 | `crop_prices` |
| 13 | NASA POWER | API REST JSON | No | 1 (respaldo) | `area_monthly_series` |
| 14 | GBIF | API REST JSON | No | 3 | `field_observations` |
| 15 | NEX-GDDP-CMIP6 | Google Earth Engine | GEE | 2 | `area_scenario_climate` |
| 16 | ECOSTRESS | AppEEARS API | Earthdata | 3 | `area_monthly_series` |

---

## 1. NOAA CPC — ONI ✅

```
GET https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
```

Formato: `SEAS YR TOTAL ANOM` (trimestre móvil, año, temperatura, anomalía).
Último valor al probar: `ASO 2026 … 2.46` → **El Niño fuerte**.

```python
import httpx

SEAS_MID = {"DJF":1,"JFM":2,"FMA":3,"MAM":4,"AMJ":5,"MJJ":6,"JJA":7,"JAS":8,"ASO":9,"SON":10,"OND":11,"NDJ":12}

def fetch_oni():
    txt = httpx.get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", timeout=30).text
    rows = []
    for line in txt.splitlines()[1:]:
        seas, yr, _total, anom = line.split()
        rows.append({"index_id": "oni", "month_date": f"{yr}-{SEAS_MID[seas]:02d}-01", "value": float(anom)})
    return rows
```

## 2. NOAA CPC — Niño 1+2 (frente a Ecuador) ✅

```
GET https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices
```

Columnas: `YR MON NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM`.
Último valor al probar: `2026 10 … 26.12 5.25` → anomalía **+5.25 °C**.

```python
def fetch_nino12():
    txt = httpx.get("https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices", timeout=30).text
    rows = []
    for line in txt.splitlines()[1:]:
        p = line.split()
        yr, mon = int(p[0]), int(p[1])
        rows.append({"index_id": "nino12_anom", "month_date": f"{yr}-{mon:02d}-01", "value": float(p[3])})
        rows.append({"index_id": "nino34_anom", "month_date": f"{yr}-{mon:02d}-01", "value": float(p[9])})
    return rows
```

---

## 3–8, 15. Google Earth Engine ✅ (IDs verificados en el catálogo)

Requisito: proyecto GEE registrado + `earthengine authenticate` + `GEE_PROJECT` en `.env`.

| Dato | ID | Bandas | Conversión |
|------|----|--------|-----------|
| ERA5-Land diario | `ECMWF/ERA5_LAND/DAILY_AGGR` | `temperature_2m`, `temperature_2m_max`, `temperature_2m_min`, `dewpoint_temperature_2m`, `total_precipitation_sum`, `u_component_of_wind_10m`, `v_component_of_wind_10m`, `surface_solar_radiation_downwards_sum`, `volumetric_soil_water_layer_1` | K − 273.15; m × 1000 = mm; J/m² ÷ 10⁶ = MJ/m² |
| GPM IMERG mensual | `NASA/GPM_L3/IMERG_MONTHLY_V07` | `precipitation` | mm/h × 24 × días |
| GPM IMERG 30 min | `NASA/GPM_L3/IMERG_V07` | `precipitation` | Sumar a diario → días > 50 mm |
| SMAP L4 | `NASA/SMAP/SPL4SMGP/008` | `sm_surface`, `sm_rootzone` | m³/m³ (2015→) |
| GLDAS (antes de 2015) | `NASA/GLDAS/V021/NOAH/G025/T3H` | `SoilMoi0_10cm_inst`, `RootMoist_inst` | kg/m² |
| MODIS NDVI | `MODIS/061/MOD13Q1` | `NDVI` | × 0.0001 |
| SRTM | `USGS/SRTMGL1_003` | `elevation` | m; pendiente con `ee.Terrain.slope` |
| Suelo pH | `OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02` | `b0` | ÷ 10 |
| Carbono orgánico | `OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M_v02` | `b0` | ver ficha |
| Cobertura | `ESA/WorldCover/v200` | `Map` | clase 10 = árboles, 40 = cultivos |
| Límites | `FAO/GAUL/2015/level1`, `level2` | `ADM1_NAME`, `ADM2_NAME` | filtrar `ADM0_NAME = 'Ecuador'` |
| CMIP6 (Fase 2) | `NASA/GDDP-CMIP6` | `tas`, `tasmax`, `tasmin`, `pr`, `hurs`, `sfcWind`, `rsds` | K − 273.15; `pr` × 86400 = mm/día. Filtros: `model` (`ACCESS-CM2`, `EC-Earth3`, `GFDL-ESM4`, `MRI-ESM2-0`), `scenario` (`historical`, `ssp245`, `ssp585`) |

### Serie diaria ERA5-Land de un área (para días favorables)

```python
import ee

def era5_daily(geom, start, end, scale=9000):
    bands = ["temperature_2m", "temperature_2m_max", "temperature_2m_min",
             "dewpoint_temperature_2m", "total_precipitation_sum", "volumetric_soil_water_layer_1"]
    col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(start, end).select(bands)
    def to_feat(img):
        v = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True)
        return ee.Feature(None, v).set("date", img.date().format("YYYY-MM-dd"))
    return [f["properties"] for f in col.map(to_feat).getInfo()["features"]]
# Pedir año por año (≈ 365 filas por llamada).
```

### Lluvia diaria GPM (para días > 50 mm)

```python
def gpm_daily(geom, start, end, scale=11000):
    col = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").filterDate(start, end).select("precipitation")
    days = ee.List.sequence(0, ee.Date(end).difference(ee.Date(start), "day").subtract(1))
    def per_day(d):
        d0 = ee.Date(start).advance(d, "day")
        img = col.filterDate(d0, d0.advance(1, "day")).sum().multiply(0.5)   # mm/h × 0.5 h
        v = img.reduceRegion(ee.Reducer.mean(), geom, scale, bestEffort=True).get("precipitation")
        return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "precip_mm": v})
    return [f["properties"] for f in ee.FeatureCollection(days.map(per_day)).getInfo()["features"]]
```

### Cantones de Ecuador

```python
cantons = (ee.FeatureCollection("FAO/GAUL/2015/level2")
           .filter(ee.Filter.eq("ADM0_NAME", "Ecuador"))
           .filter(ee.Filter.inList("ADM1_NAME", ["Los Rios", "Guayas", "Manabi", "Esmeraldas", "El Oro"])))
```

---

## 9. ECOCROP ✅

```
GET https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv
```

Codificación `latin-1`. Fila `ScientificName = "Theobroma cacao"`:
`TOPMN 21 · TOPMX 32 · TMIN 10 · TMAX 38 · ROPMN 1200 · ROPMX 3000 · RMIN 900 · RMAX 7600 ·
PHOPMN 5 · PHOPMX 6.5 · ALTMX 900 · KTMP 0 · GMIN 180 · GMAX 365`.

```python
import csv, io, httpx
url = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv"
rows = csv.DictReader(io.StringIO(httpx.get(url, timeout=60).content.decode("latin-1")))
cacao = next(r for r in rows if r["ScientificName"] == "Theobroma cacao")
```

## 10. ESPAC — INEC ✅ (sitio responde; sin API)

- Página: https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/
- Descargar por año los **tabulados** (XLSX) o la **base de datos** (CSV/SPSS).
- Buscar cultivos permanentes → **Cacao (almendra seca)**: superficie plantada, en edad
  productiva, cosechada, producción (t) **por provincia**.
- Guardar en `BACK/data/raw/espac/espac_<año>.xlsx` y normalizar con `etl_production.py`.

## 11. FAOSTAT ✅ (API pide token → usar descarga masiva)

```
GET https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Americas.zip
```

Filtrar `Area = "Ecuador"`, `Item = "Cocoa beans"`, elementos *Area harvested*, *Yield*,
*Production*. Serie nacional 1961→.

## 12. SIPA — MAG ✅ (sitio responde; descarga manual)

- http://sipa.agricultura.gob.ec/ → precios → **cacao en grano seco** (USD por quintal).
- Convertir: 1 quintal = 45.36 kg → USD/t = USD/qq × 22.05.

## 13. NASA POWER ✅ (respaldo de temperatura)

```
GET https://power.larc.nasa.gov/api/temporal/monthly/point
    ?parameters=T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR&community=AG
    &latitude=-1.80&longitude=-79.53&start=2005&end=2024&format=JSON
```

> Celda ~55 km: en Babahoyo asume 837 m de altitud (real ≈ 12 m) y subestima la temperatura.
> Usar como respaldo citado, no como fuente principal en la Costa.

## 14. GBIF — ocurrencias de *Moniliophthora roreri* ✅

```
GET https://api.gbif.org/v1/occurrence/search
    ?scientificName=Moniliophthora%20roreri&country=EC&hasCoordinate=true&limit=300
```

Al probar: **138** registros en Ecuador, **35** con coordenadas. Sirve para validar que el
índice de riesgo es alto donde la enfermedad fue observada.

```python
r = httpx.get("https://api.gbif.org/v1/occurrence/search", params={
    "scientificName": "Moniliophthora roreri", "country": "EC",
    "hasCoordinate": "true", "limit": 300}, timeout=30).json()
obs = [{"external_id": str(o["key"]), "lat": o["decimalLatitude"], "lon": o["decimalLongitude"],
        "observed_on": o.get("eventDate", "")[:10], "source": "gbif", "pathogen_id": "monilia"}
       for o in r["results"]]
```

## 16. AppEEARS — ECOSTRESS ✅ (Fase 3)

```
POST https://appeears.earthdatacloud.nasa.gov/api/login     (usuario/clave Earthdata)
POST https://appeears.earthdatacloud.nasa.gov/api/task
GET  https://appeears.earthdatacloud.nasa.gov/api/task/{task_id}
GET  https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}
```

Capas verificadas: `ECO_L2T_LSTE.002` → `LST` · `ECO_L3T_JET.002` → `ETdaily` ·
`ECO_L4T_ESI.002` → `ESI` (índice de estrés evaporativo).

---

## Atribución obligatoria

NASA (GPM, SMAP, GLDAS, MODIS, SRTM, NEX-GDDP-CMIP6, POWER, ECOSTRESS) ·
"Contains modified Copernicus Climate Change Service information" (ERA5-Land) ·
NOAA CPC · INEC (ESPAC) · FAO (FAOSTAT, ECOCROP, GAUL) · MAG (SIPA) · GBIF.org ·
ISRIC/OpenLandMap · ESA WorldCover.
