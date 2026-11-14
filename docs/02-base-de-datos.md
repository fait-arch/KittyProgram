# 2. Base de datos — diccionario de datos

Supabase · Postgres 17 + PostGIS · proyecto `chjgktgkilxjuwuuekah`.
Estado desplegado el 2026-11-14: **32 tablas, 3 vistas, 0 alertas de seguridad.** Con datos de prueba cargados (ver [08-informe-datos.md](08-informe-datos.md)).

Migraciones aplicadas, en orden: `0001_init` → `0002_fk_indexes` → `0003_field_rpc` →
`0004_more_sources` → `0005_cacaoresiliente` → `0006_revision` → `0007_limpieza` → `0008_politicas_internas`.

Principio: **guardar valores agregados (área × mes / año / escenario), nunca imágenes.**
Todo se lee públicamente; escribe solo el backend (`service_role`), salvo las observaciones y
revisiones, que cada usuario autenticado crea y edita las suyas.

## Mapa general

```
                 CATÁLOGOS                         TERRITORIO
  data_sources ─< variables                  areas (país / provincia / cantón / finca)
  crops ─< crop_requirements                   │  geom, geom_simplified, inec_dpa_code, region
        ─< crop_phenology                      │
        ─< pathogens ─< disease_thresholds     │
                                               │
  EL NIÑO                 CLIMA OBSERVADO      │        CLIMA POR ESCENARIO
  enso_index ──► v_enso_year_class   area_monthly_series ─┤   scenarios ─< area_scenario_climate
  enso_events                        area_monthly_hazard ─┤
                                     area_static_features ┤
  EXPOSICIÓN                                              │   ÍNDICES
  crop_production_stats ──────────────────────────────────┤   disease_risk_monthly
  crop_exposure                                           │   disease_risk_scenario
  crop_prices                                             │   crop_suitability
                                                          │
  MODELO                                                  │   ESTRATEGIAS
  model_versions ─< training_samples                      │   adaptation_strategies ─< strategy_effects
                 ─< loss_predictions ─────────────────────┤   loss_predictions ─< strategy_evaluations
                            │                             │                              └─< strategy_reviews
                            └──► v_loss_map (mapa)        │   zone_classification (Fase 2)
                                                          │
  VALIDACIÓN: field_observations          OPERACIÓN: etl_runs
  ENTRENAMIENTO: v_training_area_year = producción + riesgo + peligros + ENSO + aptitud
```

Convenciones: `PK` clave primaria · `FK →` clave foránea · `gen` columna calculada
automáticamente · ✅ tabla con datos cargados · ⬜ tabla vacía hasta que corra el ETL.

---

## A. Catálogos

### `data_sources` ✅ 22 filas — de dónde sale cada dato

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | Identificador corto: `gpm_imerg`, `smap_l4`, `era5_land`, `noaa_cpc`, `espac`… |
| `name` | text | Nombre completo de la fuente |
| `provider` | text | Institución: NASA, ECMWF/Copernicus, NOAA, INEC, FAO, MAG… |
| `access` | text | Cómo se accede: `gee` (Earth Engine), `power_api`, `earthdata`, `other` |
| `dataset_ref` | text | ID exacto en Earth Engine o nombre del archivo/endpoint |
| `spatial_res_m` | integer | Resolución espacial en metros (11 000 = ~11 km) |
| `temporal_res` | text | Frecuencia: `daily`, `monthly`, `8-day`, `annual`, `static`… |
| `period_start` / `period_end` | date | Desde y hasta cuándo hay datos |
| `citation` | text | Texto de atribución obligatorio (p. ej. Copernicus) |
| `url` | text | Enlace oficial |

### `variables` ✅ 24 filas — qué medimos

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `precip`, `t2m`, `rh_mean`, `ndvi`, `soil_moisture_surf`, `et0`, `wet_days`… |
| `name` | text | Nombre legible en español |
| `unit` | text | Unidad: `mm/mes`, `°C`, `%`, `m³/m³`, `días/mes`… |
| `source_id` FK → data_sources | text | Fuente principal de la variable |
| `description` | text | Explicación sencilla para el agricultor |
| `temporal_res` | text | Cómo se **guarda** la serie: `daily`, `monthly`, `static`, `derived` (calculada de otras) |

> Los umbrales de enfermedad usan estas mismas variables pero evaluadas sobre **valores diarios**
> (ver `disease_thresholds.resolution`).

### `crops` ✅ 1 fila (cacao) — catálogo de cultivos

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `cacao` |
| `name_es` | text | Nombre común |
| `scientific_name` | text | *Theobroma cacao* |
| `family` | text | Familia botánica (Malvaceae) |
| `crop_type` | text | `cash`, `staple`, `legume`, `cover`, `perennial`, `forage` |
| `region` | text[] | Regiones donde se cultiva: `{costa, amazonia}` |
| `cycle_days` | integer | Días del ciclo; `null` si es perenne |
| `is_perennial` | boolean | Perenne (el cacao: sí) |
| `temp_opt_min_c` … `rain_max_mm_cycle`, `altitude_max_m`, `ph_min`, `ph_max` | numeric | **Heredados de v1**: la fuente de verdad es `crop_requirements` |
| `kc_ini`, `kc_mid`, `kc_end` | numeric | Coeficiente de cultivo FAO-56 (demanda de agua) |
| `root_depth_m` | numeric | Profundidad de raíz |
| `n_fixing`, `n_fix_kg_ha` | boolean, numeric | Si fija nitrógeno y cuánto |
| `residue_t_ha` | numeric | Materia orgánica que deja |
| `ground_cover` | numeric 0–1 | Fracción del suelo que cubre |
| `drought_tolerance`, `waterlog_tolerance` | smallint 1–5 | Tolerancia a sequía / encharcamiento |
| `forage_value` | smallint 0–5 | Valor forrajero |
| `yield_t_ha`, `price_usd_t`, `price_updated_at` | numeric, date | Rendimiento y precio de referencia |
| `notes`, `source_ref` | text | Observaciones y fuente |

### `crop_requirements` ✅ 10 filas — requerimientos del cacao (ECOCROP)

| Columna | Tipo | Significado |
|---|---|---|
| `crop_id` PK, FK → crops | text | `cacao` |
| `parameter` PK | text | `temp_mean`, `rain_annual`, `ph`, `altitude`, `killing_temp`, `growth_days`, `light`, `soil_depth`, `soil_texture`, `drainage` |
| `opt_min` / `opt_max` | numeric | Rango **óptimo** (p. ej. 21–32 °C) |
| `abs_min` / `abs_max` | numeric | Rango **absoluto** de supervivencia (10–38 °C) |
| `value_text` | text | Valor para parámetros descriptivos ("sombra ligera", "bien drenado") |
| `unit` | text | Unidad |
| `source_ref` | text | `ECOCROP (OpenCLIM/ecocrop, EcoCrop_DB.csv)` |
| `notes` | text | Observaciones |

### `crop_phenology` ✅ 5 filas — calendario del cultivo por región

| Columna | Tipo | Significado |
|---|---|---|
| `crop_id` PK, FK → crops | text | `cacao` |
| `region` PK | text | `costa`, `sierra`, `amazonia`, `insular` |
| `stage` PK | text | `floracion`, `desarrollo_mazorca`, `cosecha_principal`, `cosecha_secundaria` |
| `months` | smallint[] | Meses del año de esa etapa, p. ej. `{1,2,3,4,5,6}` |
| `is_risk_window` | boolean | **Si es `true`, esos meses son los que suma el índice de enfermedad y el modelo** (Costa: desarrollo de mazorca, enero–junio) |
| `source_ref` | text | Fuente |
| `validated` | boolean | `true` cuando un agrónomo lo confirme |
| `notes` | text | Observaciones |

---

## B. Enfermedades

### `pathogens` ✅ 3 filas

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `monilia`, `phytophthora`, `escoba_bruja` |
| `name_es` | text | Moniliasis, Mazorca negra, Escoba de bruja |
| `scientific_name` | text | *Moniliophthora roreri*, *Phytophthora* spp., *M. perniciosa* |
| `crop_id` FK → crops | text | Cultivo que ataca |
| `organ_affected` | text | `mazorca`, `brotes` |
| `spread_by` | text[] | Cómo se dispersa: `{viento, lluvia, salpique}` |
| `description` | text | Descripción breve |

### `disease_thresholds` ✅ 7 filas — qué hace "favorable" un día

Un día es favorable para un patógeno si cumple **todas** sus reglas.

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | bigint | Autonumérico |
| `pathogen_id` FK → pathogens | text | Patógeno |
| `variable_id` FK → variables | text | Variable evaluada (`rh_mean`, `t2m`, `precip`) |
| `min_value` / `max_value` | numeric | Límites; `null` = sin límite. Ej. moniliasis: HR ≥ 80 y 20 ≤ T ≤ 28 |
| `unit` | text | Unidad del umbral |
| `resolution` | text | `daily` (por defecto): la regla se evalúa sobre el valor **diario** |
| `min_consecutive_days` | smallint | Días seguidos mínimos para contar (por defecto 1) |
| `weight` | numeric | Peso relativo de la regla |
| `validated` | boolean | `false` hasta que lo confirme INIAP / fitopatólogo |
| `source_ref`, `notes` | text | Fuente y observaciones |

---

## C. Territorio

### `areas` ⬜ — país, provincia, cantón o finca

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | uuid | Identificador |
| `kind` | text | `country`, `province`, `canton`, `field` |
| `name` | text | Nombre (como viene de GAUL) |
| `name_key` gen | text | Nombre en minúsculas y sin tildes: `los rios`. Para cruzar GAUL con INEC |
| `parent_id` FK → areas | uuid | Área contenedora (cantón → provincia) |
| `gaul_code` | integer | Código FAO GAUL |
| `inec_dpa_code` | text | **Código DPA del INEC** (provincia 2 dígitos, cantón 4). Clave para cruzar con ESPAC. Único |
| `region` | text | `costa`, `sierra`, `amazonia`, `insular`; decide la ventana de riesgo |
| `geom` | geometry(MultiPolygon, 4326) | Polígono completo, para cálculos |
| `geom_simplified` gen | geometry(MultiPolygon, 4326) | Polígono simplificado (~200 m) **para el mapa** |
| `area_ha` gen | numeric | Superficie en hectáreas |
| `owner_id` FK → auth.users | uuid | Dueño; obligatorio si `kind = 'field'` |
| `created_at` | timestamptz | Fecha de creación |

### `area_static_features` ⬜ — datos fijos del área

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Área |
| `elevation_mean_m` | numeric | Altitud media (SRTM) |
| `slope_mean_deg`, `slope_p90_deg` | numeric | Pendiente media y percentil 90 |
| `soil_ph` | numeric | pH del suelo (OpenLandMap) |
| `soil_organic_c_gkg` | numeric | Carbono orgánico |
| `clay_pct`, `sand_pct` | numeric | Textura |
| `texture_class` | text | Clase textural |
| `land_cover` | jsonb | Fracciones de cobertura: `{"cropland":0.42,"tree":0.31}` |
| `grace_tws_trend_cm_yr` | numeric | Tendencia del agua almacenada (GRACE) |
| `computed_at` | timestamptz | Cuándo se calculó |

---

## D. El Niño y escenarios

### `enso_index` ⬜ — series de NOAA

| Columna | Tipo | Significado |
|---|---|---|
| `index_id` PK | text | `oni`, `nino12_anom`, `nino3_anom`, `nino34_anom`, `nino4_anom` |
| `month_date` PK | date | Día 1 del mes (ONI: mes central del trimestre) |
| `value` | numeric | Valor del índice (°C de anomalía) |
| `phase` gen | text | `nino` / `nina` / `neutral` del **mes**: ONI ±0.5; Niño 1+2 ±0.4 |
| `fetched_at` | timestamptz | Cuándo se descargó |

### `enso_events` ⬜ — eventos identificados

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `nino_1997_98`, `nino_costero_2017`… |
| `phase` | text | `nino` o `nina` |
| `start_month` / `end_month` | date | Inicio y fin (`null` = en curso) |
| `peak_oni`, `peak_nino12` | numeric | Valor máximo alcanzado |
| `intensity` | text | `debil`, `moderado`, `fuerte`, `muy_fuerte` |
| `is_coastal` | boolean | Niño costero (Niño 1+2 alto con ONI bajo) |
| `notes` | text | Observaciones |

### `scenarios` ✅ 6 filas

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `normal`, `nino`, `nina`, `actual`, `ssp245_2050`, `ssp585_2050` |
| `name_es` | text | Nombre para la interfaz |
| `kind` | text | `historical`, `current`, `projection` |
| `phase` | smallint | Fase del proyecto en que se usa (1 o 2) |
| `period_start` / `period_end` | smallint | Años que abarca |
| `ssp` | text | `ssp245` / `ssp585` (solo proyecciones) |
| `description` | text | Cómo se construye |

### `area_scenario_climate` ⬜ — clima típico de cada escenario

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Área |
| `scenario_id` PK, FK → scenarios | text | Escenario |
| `variable_id` PK, FK → variables | text | Variable |
| `month` PK | smallint 1–12 | Mes |
| `value_mean` | numeric | Valor típico del mes |
| `value_min` / `value_max` | numeric | Rango entre años (históricos) o entre modelos (CMIP6) |
| `n_members` | smallint | Nº de años o de modelos promediados |
| `method` | text | `composite` (promedio de años), `delta` (observado + cambio CMIP6), `raw_model` |
| `computed_at` | timestamptz | Cuándo se calculó |

---

## E. Clima observado

### `area_monthly_series` ⬜ — serie mensual por variable

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Área |
| `variable_id` PK, FK → variables | text | Variable |
| `month_date` PK | date | Día 1 del mes |
| `value` | numeric | Valor del mes |
| `anomaly` | numeric | Diferencia frente al promedio histórico del mismo mes |

### `area_monthly_hazard` ⬜ — conteos de peligro por mes (independientes del patógeno)

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Área |
| `month_date` PK | date | Día 1 del mes |
| `precip_total_mm` | numeric | Lluvia total (GPM) |
| `wet_days` | smallint | Días con lluvia ≥ 1 mm |
| `heavy_rain_days` | smallint | Días con lluvia ≥ 50 mm (aguaceros) |
| `max_consecutive_wet_days` | smallint | Racha más larga de días lluviosos |
| `rh_mean` | numeric | Humedad relativa media (ERA5-Land) |
| `humid_days` | smallint | Días con HR ≥ 80 % |
| `t2m_mean` | numeric | Temperatura media |
| `hot_days` | smallint | Días con T > 32 °C (sobre el óptimo del cacao) |
| `saturated_days` | smallint | Días con suelo saturado (SMAP) |
| `n_days_with_data` | smallint | Días con dato válido (control de calidad) |
| `computed_at` | timestamptz | Cuándo se calculó |

---

## F. Exposición: producción, superficie y precios

### `crop_production_stats` ⬜ — estadísticas oficiales (ESPAC por provincia, FAOSTAT nacional)

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | bigint | Autonumérico |
| `area_id` FK → areas | uuid | Provincia o país |
| `crop_id` FK → crops | text | `cacao` |
| `year` | smallint | Año |
| `planted_ha` | numeric | Superficie plantada |
| `productive_ha` | numeric | En edad productiva |
| `harvested_ha` | numeric | Cosechada |
| `lost_ha` | numeric | Perdida |
| `production_t` | numeric | Producción en toneladas |
| `yield_t_ha` gen | numeric | **Rendimiento = producción / cosechada** (target del modelo) |
| `source_id` FK → data_sources | text | `espac` o `faostat` |
| `notes` | text | Observaciones |

Única por (área, cultivo, año, fuente).

### `crop_exposure` ⬜ — hectáreas de cacao por cantón

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Cantón |
| `crop_id` PK, FK → crops | text | `cacao` |
| `ref_year` PK | smallint | Año de referencia |
| `crop_ha` | numeric | Hectáreas |
| `method` | text | `espac_direct`, `downscaled_landcover` (repartido por cobertura), `manual` |
| `source_id` FK → data_sources | text | Fuente |

### `crop_prices` ⬜

| Columna | Tipo | Significado |
|---|---|---|
| `crop_id` PK, FK → crops | text | `cacao` |
| `month_date` PK | date | Mes |
| `market` PK | text | `nacional` por defecto |
| `product_form` PK | text | `grano_seco` por defecto |
| `price_usd_t` | numeric | Precio en USD por tonelada |
| `source_id` FK → data_sources | text | `sipa` |

---

## G. Índices calculados

### `disease_risk_monthly` ⬜ — riesgo observado por mes (alimenta el entrenamiento)

| Columna | Tipo | Significado |
|---|---|---|
| `area_id` PK, FK → areas | uuid | Área |
| `pathogen_id` PK, FK → pathogens | text | Patógeno |
| `month_date` PK | date | Mes |
| `favorable_days` | smallint | Días que cumplieron todos los umbrales |
| `max_consecutive_favorable_days` | smallint | Racha más larga de días favorables |
| `risk_index` | numeric 0–1 | `favorable_days / días del mes` |
| `n_days_with_data` | smallint | Control de calidad |
| `details` | jsonb | Desglose opcional (qué regla falló más) |
| `computed_at` | timestamptz | — |

### `disease_risk_scenario` ⬜ — riesgo típico por escenario

| Columna | Tipo | Significado |
|---|---|---|
| `area_id`, `pathogen_id`, `scenario_id`, `month` PK | — | Área, patógeno, escenario, mes |
| `risk_mean` | numeric 0–1 | Riesgo medio |
| `risk_min` / `risk_max` | numeric | Rango entre años o modelos |
| `favorable_days` | numeric | Días favorables promedio |
| `computed_at` | timestamptz | — |

### `crop_suitability` ⬜ — aptitud ECOCROP

| Columna | Tipo | Significado |
|---|---|---|
| `area_id`, `crop_id`, `scenario_id` PK | — | Área, cultivo, escenario |
| `score` | numeric 0–1 | Aptitud (1 = todo en rango óptimo) |
| `class` | text | `optima`, `apta`, `marginal`, `no_apta` |
| `limiting_factors` | text[] | Parámetros que más bajan el puntaje: `{rain_annual}` |
| `details` | jsonb | Puntaje por parámetro |
| `computed_at` | timestamptz | — |

---

## H. Modelo predictivo

### `model_versions` ⬜

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | uuid | — |
| `name` | text | `cacao_loss_v1` |
| `crop_id` FK → crops | text | Cultivo |
| `target` | text | Qué predice: `yield_anomaly_pct` |
| `algorithm` | text | `ridge`, `gbr_quantile`… |
| `features` | text[] | Variables de entrada usadas |
| `hyperparams` | jsonb | Hiperparámetros |
| `cv_scheme` | text | `leave_one_year_out` |
| `metrics` | jsonb | `{"mae":…, "skill_vs_baseline":…}` |
| `train_start_year` / `train_end_year` | smallint | Periodo de entrenamiento |
| `n_samples` | integer | Filas usadas |
| `artifact_path` | text | Ruta del `.joblib` en Storage |
| `is_active` | boolean | **Solo uno activo por cultivo** (índice único) |
| `created_at` | timestamptz | — |

### `training_samples` ⬜ — copia exacta del dataset (reproducibilidad)

| Columna | Tipo | Significado |
|---|---|---|
| `model_version_id` PK, FK → model_versions | uuid | Modelo |
| `area_id` PK, FK → areas | uuid | Área |
| `year` PK | smallint | Año |
| `features` | jsonb | Valores de entrada de esa fila |
| `target` | numeric | Valor real |
| `fold` | smallint | Pliegue de validación |
| `prediction_cv` | numeric | Predicción fuera de muestra |

### `loss_predictions` ⬜ — **la respuesta a la pregunta**

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | uuid | — |
| `model_version_id` FK → model_versions | uuid | Modelo que predijo |
| `area_id` FK → areas | uuid | Cantón / provincia |
| `crop_id` FK → crops | text | `cacao` |
| `scenario_id` FK → scenarios | text | `normal`, `nino`, `actual`, `ssp245_2050`… |
| `loss_pct` | numeric | Pérdida esperada de rendimiento (%) |
| `loss_pct_low` / `loss_pct_high` | numeric | Intervalo (percentiles 10 y 90) |
| `exposed_ha` | numeric | Hectáreas en juego (congeladas al predecir) |
| `expected_yield_t_ha` | numeric | Rendimiento esperado sin pérdida |
| `loss_t` | numeric | Toneladas perdidas |
| `price_usd_t` | numeric | Precio usado (congelado) |
| `loss_usd` | numeric | Pérdida en dólares |
| `risk_class` | text | `bajo` <5 % · `medio` 5–15 % · `alto` 15–30 % · `muy_alto` >30 % |
| `top_factors` | jsonb | Factores que más explican: `[{"feature":"fav_days_monilia","contribution":4.1}]` |
| `created_at` | timestamptz | — |

Única por (modelo, área, cultivo, escenario).

---

## I. Estrategias de adaptación

### `adaptation_strategies` ✅ 4 filas

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | text | `actual`, `sanitario`, `drenaje_sombra`, `diversificacion` |
| `name_es` | text | Nombre |
| `description` | text | En qué consiste |
| `cost_usd_ha_year` | numeric | Costo por hectárea y año (por completar) |
| `applies_to_zones` | text[] | Zonas donde aplica: `{manejo, critica}` |
| `evidence` | text | Resumen de evidencia |
| `source_ref` | text | Fuente |
| `validated` | boolean | Confirmada por experto |

### `strategy_effects` ✅ 7 filas — cuánto reduce cada estrategia cada problema

| Columna | Tipo | Significado |
|---|---|---|
| `strategy_id` PK, FK → adaptation_strategies | text | Estrategia |
| `target` PK | text | `monilia`, `phytophthora`, `escoba_bruja`, `encharcamiento`, `calor`, `ingreso` |
| `reduction_pct_low` / `reduction_pct_high` | numeric 0–100 | Rango de reducción de pérdida (**por completar con literatura / INIAP**) |
| `source_ref` | text | Fuente |
| `validated` | boolean | Confirmado |
| `notes` | text | Observaciones |

### `strategy_evaluations` ⬜ — estrategias evaluadas para cada predicción

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | uuid | — |
| `prediction_id` FK → loss_predictions | uuid | Predicción (área × escenario) |
| `strategy_id` FK → adaptation_strategies | text | Estrategia |
| `rank` | smallint | Orden recomendado |
| `expected_loss_pct` | numeric | Pérdida esperada aplicando la estrategia |
| `avoided_loss_usd` | numeric | Pérdida evitada en USD |
| `net_benefit_usd` | numeric | Pérdida evitada − costo |
| `why` | text | Por qué se sugiere |
| `evidence` | jsonb | `[{variable_id, source_id, statement}]` |
| `data_gaps` | text[] | Qué datos faltan |
| `risks` | text[] | Qué debe validar un técnico |

### `zone_classification` ⬜ *(Fase 2)* — matriz aptitud futura × riesgo Niño

| Columna | Tipo | Significado |
|---|---|---|
| `area_id`, `crop_id`, `future_scenario_id` PK | — | Área, cultivo, escenario 2050 |
| `zone_class` | text | `segura`, `manejo`, `transicion`, `critica` |
| `suitability_now` / `suitability_future` | numeric | Aptitud actual y futura |
| `nino_risk` | numeric | Riesgo en año Niño |
| `computed_at` | timestamptz | — |

---

## J. Validación en campo

### `field_observations` ⬜

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | bigint | — |
| `area_id` FK → areas | uuid | Área (opcional) |
| `pathogen_id` FK → pathogens | text | Enfermedad observada |
| `observed_on` | date | Fecha |
| `lat`, `lon` | numeric | Coordenadas |
| `pods_total`, `pods_diseased` | integer | Mazorcas contadas y enfermas |
| `incidence_pct` gen | numeric | `100 × enfermas / total` |
| `severity` | smallint 0–5 | Severidad |
| `source` | text | `gbif`, `tecnico`, `agricultor` |
| `external_id` | text | ID en GBIF (único por fuente) |
| `observer_id` FK → auth.users | uuid | Quién la registró |
| `notes`, `created_at` | — | — |

### `strategy_reviews` ⬜ — opinión experta sobre una recomendación

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | bigint | — |
| `evaluation_id` FK → strategy_evaluations | uuid | Recomendación evaluada |
| `reviewer_id` FK → auth.users | uuid | Quién opina |
| `reviewer_role` | text | `agricultor`, `agronomo`, `fitopatologo`, `otro` |
| `verdict` | text | `de_acuerdo`, `parcial`, `en_desacuerdo` |
| `comment`, `created_at` | — | — |

---

## K. Operación

### `etl_runs` ⬜ — registro de cargas

| Columna | Tipo | Significado |
|---|---|---|
| `id` PK | bigint | — |
| `script` | text | `etl_enso`, `etl_climate`, `etl_production`… |
| `params` | jsonb | `{"provinces":[…],"years":"2001-2025"}` |
| `started_at` / `finished_at` | timestamptz | Inicio y fin |
| `status` | text | `running`, `done`, `error` |
| `rows_written` | integer | Filas escritas |
| `error`, `notes` | text | Error y observaciones |

---

## L. Vistas

### `v_enso_year_class` — clasificación de cada año (regla única)

| Columna | Significado |
|---|---|
| `year` | Año |
| `oni_jan_jun`, `oni_max_jan_jun` | ONI medio y máximo de enero a junio |
| `nino12_anom_jan_jun`, `nino12_max_jan_jun` | Niño 1+2 medio y máximo |
| `enso_class` | `nino` si ONI ≥ 0.5 **o** Niño 1+2 ≥ 0.4 · `nina` si ONI ≤ −0.5 · `neutral` |
| `is_coastal_nino` | Niño costero: Niño 1+2 ≥ 0.4 con ONI < 0.5 (p. ej. 2017) |

### `v_training_area_year` — dataset de entrenamiento (área × año)

Une `crop_production_stats` con `disease_risk_monthly` y `area_monthly_hazard` **sumados solo en
la ventana de riesgo** de `crop_phenology` (Costa: enero–junio), más `v_enso_year_class` y
`crop_suitability`.

| Columna | Origen |
|---|---|
| `area_id`, `crop_id`, `year` | Clave |
| `yield_t_ha`, `harvested_ha`, `lost_ha`, `production_t` | Producción real (target) |
| `fav_days_monilia`, `fav_days_phytophthora`, `fav_days_escoba`, `risk_index_mean`, `max_consec_favorable` | Riesgo de enfermedad |
| `precip_total_mm`, `wet_days`, `heavy_rain_days`, `max_consecutive_wet_days`, `rh_mean`, `humid_days`, `t2m_mean`, `hot_days`, `saturated_days` | Peligros climáticos |
| `oni_jan_jun`, `nino12_anom_jan_jun`, `enso_class`, `is_coastal_nino` | El Niño |
| `suitability_now` | Aptitud ECOCROP en escenario `normal` |

### `v_loss_map` — una fila por área × escenario para el mapa

`area_id`, `name`, `kind`, `region`, `inec_dpa_code`, `province`, `area_ha`, `geom`
(simplificada), `crop_id`, `scenario_id`, `loss_pct`, `loss_pct_low`, `loss_pct_high`,
`exposed_ha`, `loss_t`, `loss_usd`, `risk_class`, `top_factors`, `model_name`.
Solo incluye el modelo activo.

---

## M. Tablas de la v1 (rotación de cultivos)

Se **eliminaron** en la migración `0007_limpieza` (estaban vacías): `analysis_runs`,
`rotation_strategies`, `expert_reviews`, `area_climatology`, `field_current_rotation` y
`field_priorities`. Las reemplazan `loss_predictions`, `strategy_evaluations`, `strategy_reviews`,
`area_scenario_climate` y `area_monthly_series`.

Se conserva `field_profiles` (datos de la finca que da el agricultor: `irrigation`, `water_source`,
`soil_texture_obs`, `soil_ph_obs`, `equipment[]`, `market_access`, `notes`) para la Fase 3.

---

## Funciones

| Función | Esquema | Uso |
|---|---|---|
| `can_read_area(uuid)`, `owns_area(uuid)` | `private` | Permisos de RLS sobre fincas |
| `create_field(nombre, geojson, padre)`, `update_field_geom(id, geojson)` | `public` (RPC) | Crear / editar fincas desde GeoJSON (Fase 3) |

## Seguridad (RLS)

| Tablas | Lectura | Escritura |
|---|---|---|
| Catálogos, clima, índices, modelo, predicciones, estrategias | Pública | Solo backend (`service_role`) |
| `etl_runs`, `training_samples` (internas) | **Nadie** (privilegios revocados + política `solo backend`) | Solo backend |
| `areas` tipo `field` y `field_profiles` | Solo el dueño | Solo el dueño |
| `field_observations`, `strategy_reviews` | Pública | Cada usuario autenticado crea y edita las suyas |

## Pendientes de contenido (no de estructura)

- `strategy_effects.reduction_pct_*` y `adaptation_strategies.cost_usd_ha_year`: completar con literatura / INIAP.
- `disease_thresholds` y `crop_phenology`: marcar `validated = true` cuando lo confirme un experto.
- Variedad de cacao (Nacional vs CCN-51): no se modela; se documenta como limitación.
