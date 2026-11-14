# 2. Base de datos (Supabase · Postgres + PostGIS)

Migración: [`supabase/migrations/0005_cacaoresiliente.sql`](../supabase/migrations/0005_cacaoresiliente.sql)
— se aplica **sobre 0001–0004**. Probada en Supabase dentro de una transacción con *rollback*
(crea 21 tablas + 1 vista; la clasificación de fases ENSO funciona).

Principio: **guardar valores agregados (área × mes / año / escenario), nunca imágenes**.

## Mapa de datos: qué controlamos y de dónde sale

| Bloque | Qué guarda | Tablas | Fuente |
|--------|-----------|--------|--------|
| **A. Cultivo** | Requerimientos del cacao | `crops`, `crop_requirements` | ECOCROP |
| **B. Enfermedades** | Patógenos y umbrales climáticos | `pathogens`, `disease_thresholds` | Literatura (por validar con INIAP) |
| **C. El Niño** | ONI, Niño 1+2, eventos, escenarios | `enso_index`, `enso_events`, `scenarios` | NOAA CPC |
| **D. Clima** | Serie mensual observada y climatología por escenario | `area_monthly_series` *(0001)*, `area_scenario_climate` | ERA5-Land, GPM, SMAP, MODIS, NEX-GDDP-CMIP6 |
| **E. Exposición** | Producción, superficie, rendimiento, precios | `crop_production_stats`, `crop_exposure`, `crop_prices` | ESPAC, FAOSTAT, SIPA |
| **F. Índices** | Riesgo de enfermedad y aptitud | `disease_risk_monthly`, `disease_risk_scenario`, `crop_suitability` | Calculado (ETL) |
| **G. Modelo** | Versiones, dataset, predicciones de pérdida | `model_versions`, `training_samples`, `loss_predictions` | Entrenamiento |
| **H. Estrategias** | Catálogo y evaluación por cantón | `adaptation_strategies`, `strategy_evaluations`, `zone_classification` | Literatura + cálculo |
| **I. Validación** | Observaciones de campo y revisiones | `field_observations`, `strategy_reviews` | GBIF, técnicos, agricultores |
| *(0001)* | Territorio | `areas` (país, provincia, cantón, finca) | FAO GAUL |
| *(0001)* | Catálogos | `data_sources`, `variables` | — |

## Diagrama

```
crops ─┬─< crop_requirements
       ├─< pathogens ─< disease_thresholds >── variables >── data_sources
       ├─< crop_production_stats >── areas
       ├─< crop_exposure        >── areas
       └─< crop_prices

areas ─┬─< area_monthly_series        (observado, mensual)
       ├─< area_scenario_climate >── scenarios
       ├─< disease_risk_monthly  >── pathogens         ──┐
       ├─< disease_risk_scenario >── pathogens, scenarios │
       ├─< crop_suitability      >── scenarios            │  v_training_area_year
       ├─< loss_predictions >── model_versions, scenarios │  (vista para el modelo)
       │        └─< strategy_evaluations >── adaptation_strategies
       │                 └─< strategy_reviews
       ├─< zone_classification >── scenarios   (Fase 2)
       └─< field_observations  >── pathogens

enso_index, enso_events  (globales, por mes)
model_versions ─< training_samples >── areas
```

## Variables que controlamos

### Clima (por área y mes)

| `variable_id` | Unidad | Fuente | Para qué |
|---------------|--------|--------|----------|
| `t2m`, `t2m_max`, `t2m_min` | °C | ERA5-Land | Rango óptimo del cacao, umbral de patógenos |
| `rh_mean` | % | ERA5-Land (punto de rocío) | **Clave**: días húmedos para moniliasis |
| `precip` | mm/mes | GPM IMERG | Lluvia anual vs requerimiento; salpique (mazorca negra) |
| `wet_days` | días/mes | GPM IMERG | Días con lluvia ≥ 1 mm |
| `heavy_rain_days` | días/mes | GPM IMERG | Lluvia ≥ 50 mm: caída de flores, inundación |
| `soil_moisture_surf`, `soil_moisture_root` | m³/m³ | SMAP | Suelo saturado |
| `saturated_days` | días/mes | SMAP | Asfixia radicular |
| `hot_days` | días/mes | ERA5-Land | Días > 32 °C (sobre el óptimo) |
| `et0`, `water_balance` | mm/mes | ERA5-Land (FAO-56), GPM | Déficit/exceso hídrico |
| `ndvi`, `ndvi_anom` | índice | MODIS | Vigor del cacaotal; caída tras eventos |
| `temp_change_c`, `precip_change_pct` | °C, % | NEX-GDDP-CMIP6 | Fase 2 |

### Estáticas (por área)

`area_static_features` *(0001)*: altitud y pendiente (SRTM), pH, carbono orgánico, arcilla,
arena (OpenLandMap), cobertura (WorldCover).

### Requerimientos del cacao (ECOCROP) — `crop_requirements`

`temp_mean` 21–32 °C (abs 10–38) · `rain_annual` 1200–3000 mm (abs 900–7600) · `ph` 5.0–6.5 ·
`altitude` ≤ 900 m · `killing_temp` 0 °C · `growth_days` 180–365 · `light` despejado a sombra
ligera · `soil_depth` profundo · `soil_texture` pesado/orgánico · `drainage` bien drenado.

### Umbrales de enfermedad — `disease_thresholds` (referenciales, `validated = false`)

| Patógeno | Regla para "día favorable" |
|----------|----------------------------|
| Moniliasis | `rh_mean` ≥ 80 % **y** 20 ≤ `t2m` ≤ 28 °C |
| Mazorca negra | `precip` ≥ 1 mm **y** `rh_mean` ≥ 85 % **y** 20 ≤ `t2m` ≤ 30 °C |
| Escoba de bruja | `rh_mean` ≥ 80 % **y** 20 ≤ `t2m` ≤ 30 °C |

Se cambian sin tocar código (son filas). Cuando un experto los confirme → `validated = true`.

### El Niño — `enso_index`

| `index_id` | Fuente | Fase (columna calculada) |
|------------|--------|--------------------------|
| `oni` | NOAA CPC `oni.ascii.txt` | Niño ≥ +0.5 · Niña ≤ −0.5 |
| `nino12_anom` | NOAA CPC `sstoi.indices` | Niño ≥ +0.4 · Niña ≤ −0.4 (Niño costero) |

### Escenarios — `scenarios`

| id | Fase | Qué es |
|----|------|--------|
| `normal` | 1 | Promedio de años neutros 2001–2025 |
| `nino` | 1 | Promedio de años Niño |
| `nina` | 1 | Promedio de años Niña |
| `actual` | 1 | Temporada en curso (ENSO actual) |
| `ssp245_2050` | 2 | CMIP6 SSP2-4.5, 2041–2060, método delta |
| `ssp585_2050` | 2 | CMIP6 SSP5-8.5, 2041–2060, método delta |

### Exposición

| Tabla | Granularidad | Campos clave |
|-------|--------------|--------------|
| `crop_production_stats` | provincia × año (ESPAC) / país × año (FAOSTAT) | `planted_ha`, `harvested_ha`, `lost_ha`, `production_t`, `yield_t_ha` (calculado) |
| `crop_exposure` | cantón × año | `crop_ha` y método (`espac_direct`, `downscaled_landcover`) |
| `crop_prices` | mes | `price_usd_t` (grano seco) |

## Vista de entrenamiento — `v_training_area_year`

Une, por **área × año**, el rendimiento (ESPAC) con los acumulados de **enero–junio**
(época lluviosa de la Costa): días favorables a moniliasis y mazorca negra, días de lluvia
intensa, días saturados, índice de riesgo medio, ONI y Niño 1+2 medios, y aptitud actual.
El script de entrenamiento la lee directamente ([05-modelo-predictivo.md](05-modelo-predictivo.md)).

## Seguridad (RLS)

- **Todo es de lectura pública** (son datos agregados, no personales).
- **Escribe solo el backend** con `service_role` (ETL, modelo, predicciones).
- `field_observations` y `strategy_reviews`: un usuario autenticado crea/edita las suyas.

## Tamaño estimado

~220 cantones + 24 provincias × 15 variables × 300 meses ≈ 1.1 M filas en
`area_monthly_series` (≈ 100 MB). Para el MVP basta con las **provincias cacaoteras de la
Costa** (≈ 80 cantones) → < 40 MB. Plan gratuito: 500 MB.
