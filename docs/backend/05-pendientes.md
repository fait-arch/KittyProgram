# 5. Pendientes, inconsistencias y decisiones

Revisión del repo al 2026-11-14 (ramas `diego/supabase-docs` y `beltranfuego`).

## Inconsistencias encontradas

| # | Dónde | Qué pasa | Propuesta | Dueño |
|---|-------|----------|-----------|-------|
| I1 | `BACK/docs/` vs `docs/` | Conviven dos productos: **AgroRotación UIDE** (rotación por finca, banano; tablas `field_*`, `analysis_runs`, `rotation_strategies`, `expert_reviews` de 0001) y **CacaoResiliente** (0005). | El producto es CacaoResiliente. Las tablas de 0001 no se usan en F1–F2 (quedan para F3 "finca"). Marcar `BACK/docs/` como **v1 / histórico**. | Todos |
| I2 | `docs/03-backend.md` | Dice "Base: el backend existente de `AgriculturalUIDE/BACK`", pero ese código **no está en este repo** (`BACK/` solo tiene docs). | Decisión D4. | Backend |
| I3 | rama `beltranfuego` → `nasa_data` | Saca `t2m`, `rh2m` de **NASA POWER**; el plan usa **ERA5-Land** para temperatura y `rh_mean` (los umbrales de enfermedad usan `rh_mean` y `t2m`). Con POWER, en Babahoyo la T sale ~5 °C más fría (celda a 837 m). | El ETL de enfermedad debe usar ERA5-Land (`rh_mean` desde punto de rocío). `nasa_data` sirve para exploración/notebooks. | Datos |
| I4 | rama `beltranfuego` | Partió de un commit anterior: no tiene 0004/0005 ni `docs/`. | Rebasar sobre `diego/supabase-docs` antes de unir. | Beltrán |
| I5 | `nasa_data/series.py` | `precip` = mm/h × 24 × **30.4** (mes fijo). | Usar días reales del mes (como en `docs/APIS-DATOS.md`). Error ±3 %. | Datos |
| I6 | `loss_predictions.top_factors` | El comentario SQL usa `contribution`; el ejemplo de API usa `contribution_pct`. | Contrato fijo: `{feature, value, contribution_pct}` ([03](03-integracion-ml.md)). | ML |
| I7 | `loss_predictions` | No guarda el vector de features → el what-if no tiene de dónde partir. | ✅ Resuelto en backend: features desde el bundle del modelo o reconstruidas de `disease_risk_scenario`. | Backend |
| I8 | `areas.geom` | PostgREST no devuelve GeoJSON de PostGIS directamente; `/areas/geojson` no es implementable sin RPC. | ✅ Resuelto: 0006 agregó `geom_simplified`; el backend la sirve como GeoJSON. | — |
| I9 | `v_training_area_year` | `heavy_rain_days` y `saturated_days` se leen **solo de las filas de `monilia`**. | El ETL debe llenar esas columnas en las filas de `monilia` (o en todas). Documentarlo en el ETL. | Datos |
| I10 | `disease_thresholds` | La regla de mazorca negra usa `variable_id='precip'` con unidad **mm/día**, pero la variable `precip` es mm/mes. | Correcto si el ETL evalúa las reglas con datos **diarios** en memoria (como dice 03-backend). Solo aclararlo. | Datos |
| I11 | Nombres de provincias | GAUL los guarda sin tildes (`Los Rios`, `Manabi`). | La API acepta nombre o uuid; el front muestra `name` tal cual o mapea a tildes. | Front |
| I12 | Repo | `main` no tiene commits; `origin/HEAD` apunta a `diego/supabase-docs`. | Unir `diego/supabase-docs` a `main` y abrir PRs contra `main`. | Diego |

| I13 | `ml/features.py` (Arthur) vs `disease_thresholds` (BD) | Umbrales distintos: moniliasis HR ≥ **85 %** y 22–30 °C en ML vs **80 %** y 20–28 °C en la BD; mazorca negra HR ≥ 90 % y lluvia ≥ 10 mm vs 85 % y ≥ 1 mm; aguacero ≥ 30 mm sobre la media del área vs ≥ 50 mm. | Acordar **una** fuente de verdad (la BD) o documentar por qué el modelo usa otros. El backend muestra los de la BD. | Datos + ML |
| I14 | Nombres de features | ML usa `nino12_jan_jun`, `suitability`, `rain_total`, `y_anom_prev`; la vista `v_training_area_year` usa `nino12_anom_jan_jun`, `suitability_now`, `precip_total_mm`. | El backend acepta ambos (alias en `predictor.py`, etiquetas en `labels.py`). Ideal: unificar. | ML + Datos |
| I15 | Clases de riesgo | `bajo < 5 % · medio 5–15 · alto 15–30 · muy_alto > 30` están propuestas, **sin validar**. | Validar los cortes con INIAP; viven en `labels.RISK_CLASSES`. | Todos |
| I16 | Supabase | ✅ Resuelto: el proyecto correcto es `chjgktgkilxjuwuuekah`. | — |

## ⚠ Supuestos del backend: porcentajes y costos de las estrategias

`strategy_effects.reduction_pct_low/high` y `adaptation_strategies.cost_usd_ha_year` están
**vacíos** en la BD. Mientras Datos no los llene, el backend usa estos valores, que **no salen
de ninguna fuente**: los puse yo como orden de magnitud para que la herramienta funcione. Todas
las respuestas los marcan con `"validated": false` y `"source": "supuesto del backend (por validar)"`.

| Estrategia | Objetivo | Reducción supuesta | Costo supuesto (USD/ha/año) |
|------------|----------|-------------------|-----------------------------|
| Manejo sanitario | moniliasis | 25–50 % | 120 |
| | mazorca negra | 20–40 % | |
| | escoba de bruja | 20–40 % | |
| Drenaje + sombra | mazorca negra | 15–35 % | 180 |
| | encharcamiento | 30–60 % | |
| | calor | 20–40 % | |
| Diversificación | ingreso protegido | 15–30 % | 90 |
| Manejo actual | — | 0 % | 0 |

Otros supuestos del mismo cálculo:

- **Peso de problemas no fúngicos en la pérdida:** encharcamiento 15 %, calor 5 %. El 80 %
  restante se reparte entre patógenos según su riesgo en la ventana de cultivo del cantón.
- **Atributos para el ranking por prioridades** (0–1): ver la tabla de D3 arriba.

**Por qué importa:** con estos costos, en los datos de prueba ninguna estrategia sale con
beneficio neto positivo en un solo año Niño. El resultado depende casi por completo de estos
números. **Antes de la demo hay que reemplazarlos** con literatura o INIAP.

**Cómo reemplazarlos (sin tocar código):** llenar en Supabase `strategy_effects.reduction_pct_low/high`
(+ `source_ref`, `validated`) y `adaptation_strategies.cost_usd_ha_year`. El backend usa
automáticamente los de la BD cuando existen y luego hay que llamar a `POST /api/v1/admin/cache/clear`.
Los valores por defecto están en `BACK/app/services/strategies.py` (`DEFAULT_EFFECTS`,
`DEFAULT_COST_USD_HA`, `NON_DISEASE_WEIGHT`, `ATTRIBUTES`).

## Riesgo con el reto

El reto *Field Shift* pide explorar **rotaciones de cultivos** y comparar **≥ 3 estrategias
incluida la actual**. El cacao es perenne, así que "rotación" pesa poco. Cubrirlo explícitamente:

- La estrategia **diversificación** incluye cultivos intercalados (plátano, maíz, leguminosas)
  durante la renovación o el cacao joven → es la parte de "rotación".
- Mostrar en la UI "periodos de suelo desnudo / meses vulnerables" (del riesgo mensual), que
  el reto menciona.
- Las prioridades del agricultor (D3) responden al punto "farmer priorities".

## Decisiones (tomadas el 2026-11-14)

| # | Decisión | Resultado |
|---|----------|-----------|
| D1 | Cultivo | ✅ **Cacao**. La API sigue siendo agnóstica (`crop`). |
| D2 | ¿Quién evalúa las estrategias? | ✅ **Backend**, al vuelo, con `strategy_effects`. Además, **insights y recomendaciones con IA** por cantón. |
| D8 | Proveedor de IA | ✅ **DeepSeek** (`AI_PROVIDER=deepseek`); Claude queda como alternativa (`AI_PROVIDER=anthropic`). |
| D3 | Ranking por prioridades | ✅ Ponderado en vivo (fórmula abajo). Los atributos de cada estrategia viven en el código del backend (no se toca la BD). |
| D4 | Código base | ✅ **Desde cero**. `BACK/docs/` (v1) no se usa. |
| D5 | ¿Dónde corre la demo? | Local con `--host 0.0.0.0` (pendiente decidir hosting). |
| D6 | Modelo ML | ✅ **Dentro del backend**: ML entrega el `.joblib` (+ `ml/inference.py` opcional) y se copia a `BACK/models/`. |
| D7 | Base de datos | ✅ **El backend no modifica el esquema**. Lo hace solo Datos. |

### D3 · Fórmula de prioridades

Prioridades del agricultor `w ∈ [0,5]`: `ingreso`, `costo`, `suelo`, `agua`, `mano_obra`.

```
score(e) = w_ingreso · norm(avoided_loss_usd)       # cuánto dinero salva
         + w_costo   · (1 − norm(cost_usd_ha_year))  # cuánto cuesta
         + w_suelo   · attributes.soil               # mejora el suelo (0–1)
         + w_agua    · attributes.water              # maneja el exceso/déficit de agua (0–1)
         + w_mano_obra · (1 − attributes.labor)      # cuánta mano de obra pide (0–1)
```

`norm` = min-max entre las estrategias del mismo cantón. Empate → `net_benefit_usd`.
`actual` siempre aparece (aunque quede última). Atributos por defecto (en
`BACK/app/services/strategies.py`, valores REFERENCIALES por validar con INIAP):

| Estrategia | soil | water | labor |
|------------|------|-------|-------|
| actual | 0.0 | 0.0 | 0.0 |
| sanitario | 0.2 | 0.0 | 0.8 |
| drenaje_sombra | 0.6 | 0.9 | 0.5 |
| diversificacion | 0.7 | 0.4 | 0.6 |

## Tareas

### Backend (nosotros)

| # | Tarea | Estado |
|---|-------|--------|
| B1 | Esqueleto FastAPI (`core/`, `/health`, CORS, errores, caché) | ✅ |
| B2 | Fuente mock con el mismo contrato | ✅ |
| B3 | Catálogos + ENSO (con respaldo NOAA en vivo) + escenarios | ✅ |
| B4 | Áreas + GeoJSON + lookup por punto | ✅ |
| B5 | Pérdidas + mapa GeoJSON + resumen + detalle | ✅ |
| B6 | Estrategias al vuelo + ranking por prioridades | ✅ |
| B7 | `/predict` what-if con el `.joblib` | ✅ (falta el modelo real de ML) |
| B8 | `/point/climate` NASA POWER | ✅ (probado en vivo) |
| B9 | Admin (caché, recarga de modelo) | ✅ |
| B10 | F2: `/compare`, `/zones` | ✅ |
| B11 | Insights y preguntas con IA (DeepSeek por defecto, Claude opcional) | ✅ (probado con API simulada; falta `DEEPSEEK_API_KEY`) |
| B12 | Probar contra Supabase real | ✅ Todas las rutas responden contra `chjgktgkilxjuwuuekah` (catálogos con datos; territorio, ENSO y pérdidas vacíos hasta el ETL). Falta la key publishable |
| B14 | Integrar el bundle de Arthur (`ml/artifacts/`) | ⏳ backend listo (alias + `area_means`), falta el `.joblib` |
| B13 | Hosting de la demo | ⏳ |

### Datos (Diego)

- Llenar `strategy_effects.reduction_pct_*` y `adaptation_strategies.cost_usd_ha_year` con literatura/INIAP.
- Llenar `areas` (cantones de la Costa), `enso_index`, `area_scenario_climate`, `disease_risk_*`,
  `crop_suitability`, `crop_exposure`, `crop_prices`.
- Resolver I3, I5, I9.

### ML

- Checklist de [03-integracion-ml.md](03-integracion-ml.md) § 6.

### Front

- Consumir [02-endpoints.md](02-endpoints.md) contra el backend en `DATA_SOURCE=mock` (ya funciona).
- Capas raster NASA (NDVI MODIS, lluvia IMERG) directo de **GIBS WMTS** (sin key):
  `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{Layer}/default/{Time}/GoogleMapsCompatible_Level{N}/{z}/{y}/{x}.png`
