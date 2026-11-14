# 6. Caché de datos NASA

Objetivo: calcular cada dato satelital **una sola vez por área** y servirlo desde Supabase.
Evita los límites de GEE (≈40 peticiones simultáneas, ≈5 min por cálculo, cuota mensual de
cómputo) y hace que la demo cargue al instante.

## Patrón *cache-aside*

```
GET /areas/{id}/climatology?variables=precip,ndvi
        │
        ▼
climate_repo.get(area_id, variables) ──► ¿todas las variables en caché y frescas?
        │ sí                                   │ no (faltan algunas)
        ▼                                      ▼
   devolver                     climate_service.compute(area, faltantes)
                                   ├── GEE: precip, ndvi, lst, et, smap, grace, srtm
                                   └── POWER: t2m, t2m_min/max, rh2m, solar, et0
                                        │
                                        ▼
                         climate_repo.upsert(...)  (service_client)
                                        │
                                        ▼
                                    devolver
```

**Fresco** = `computed_at` de menos de 30 días (climatologías) o 7 días (series recientes).

## Qué calcula cada fuente

| Variable | Fuente | Cálculo |
|----------|--------|---------|
| `precip` | GEE `NASA/GPM_L3/IMERG_MONTHLY_V07` | `precipitation` (mm/h) × horas del mes → media por mes 2005–2025 |
| `heavy_rain_days` | GEE GPM IMERG diario | Días con > 50 mm, media por mes |
| `soil_moisture_surf/root` | GEE `NASA/SMAP/SPL4SMGP/008` | `sm_surface`, `sm_rootzone`, media mensual 2016–2025 |
| `ndvi` | GEE `MODIS/061/MOD13Q1` | `NDVI × 0.0001`, media mensual |
| `lst_day` | GEE `MODIS/061/MOD11A2` | `LST_Day_1km × 0.02 − 273.15` |
| `et_actual` | GEE `MODIS/061/MOD16A2GF` | `ET × 0.1` (mm/8 días) → mm/mes |
| `t2m`, `t2m_max`, `t2m_min`, `rh2m`, `solar_rad` | NASA POWER (punto = centroide) | API `climatology/point`, comunidad `AG` |
| `et0` | FAO-56 Penman-Monteith calculado con datos POWER (`T2M_MAX`, `T2M_MIN`, `RH2M`, `WS2M`, `ALLSKY_SFC_SW_DWN`) | mm/mes. **No usar `EVPTRNS`**: es evapotranspiración *real* del modelo (p. ej. 0.06 mm/día en noviembre en Babahoyo), no la de referencia |
| `frost_days` | NASA POWER diario | Días con `T2M_MIN` < 2 °C |
| `water_balance` | Derivado | `precip − et0` |
| Estáticos | GEE SRTM, OpenLandMap, WorldCover, GRACE | Media/percentil sobre el polígono |

## Reglas para no chocar con los límites de GEE

1. **Escala gruesa** en series: `reduceRegion(scale=5000, bestEffort=True, maxPixels=1e9)`.
2. **Una sola petición por variable**: agregar los 12 meses en el servidor de GEE con
   `ee.List.sequence(1, 12).map(...)` y hacer un único `getInfo()`.
3. **Un cálculo a la vez por área**: usar un candado en memoria
   (`dict[area_id, threading.Lock]`) para que dos usuarios no disparen el mismo cálculo.
4. **Precalentar la demo**: script que recorre los cantones elegidos y llena la caché:

```bash
venv\Scripts\python -m app.scripts.warm_cache --province "Los Rios"
```

## NASA POWER: ejemplo

```python
import httpx

POWER = "https://power.larc.nasa.gov/api/temporal/climatology/point"

def power_climatology(lat: float, lon: float) -> dict:
    r = httpx.get(POWER, params={
        "parameters": "T2M,T2M_MAX,T2M_MIN,RH2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR",
        "community": "AG", "latitude": lat, "longitude": lon, "format": "JSON",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]["parameter"]   # {"T2M": {"JAN": 23.0, …, "ANN": 23.2}, …}
```

Resolución ≈ 0.5° (~55 km): sirve para clima regional, no para diferencias dentro de una finca.
Para eso se usan las capas de GEE (MODIS 250 m–1 km, SRTM 30 m).

## Guardado

```python
rows = [{"area_id": area_id, "variable_id": var, "month": m,
         "mean": v["mean"], "p10": v["p10"], "p90": v["p90"],
         "n_years": n, "period_start": 2005, "period_end": 2025}
        for m, v in monthly.items()]
service_client().table("area_climatology").upsert(rows).execute()
```

## Limitaciones a comunicar en la app

- Los satélites miden **promedios de píxel** (250 m a 55 km), no un punto exacto de la finca.
- SMAP mide solo los primeros centímetros del suelo en superficie; la zona de raíces es modelada.
- Nubes y años sin datos reducen `n_years`: mostrarlo como **incertidumbre**.
- Toda recomendación debe validarla un agricultor o agrónomo local.
