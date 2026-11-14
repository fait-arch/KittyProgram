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
| D2 | ¿Quién evalúa las estrategias? | ✅ **Backend**, al vuelo, con `strategy_effects`. Además, **insights y recomendaciones con IA** (Claude) por cantón. |
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

| # | Tarea | Hecho cuando |
|---|-------|--------------|
| B1 | Esqueleto FastAPI (`core/`, `/health`, CORS, errores, caché) | `/health` responde |
| B2 | Mocks JSON de `/losses`, `/detail`, `/strategies`, `/enso/current` | El front puede trabajar sin BD |
| B3 | Catálogos + ENSO + escenarios (#2–#10) | Datos reales de 0005 |
| B4 | Áreas + GeoJSON + lookup (#11–#14) | Mapa de cantones dibuja |
| B5 | Pérdidas + resumen + detalle (#20–#22) | Panel del cantón con datos reales |
| B6 | Job `evaluate_strategies` + endpoint #23 con prioridades | 4 estrategias por cantón |
| B7 | `/predict` what-if (#24) | Slider cambia la pérdida |
| B8 | `/point/climate` POWER (#27) | Clic libre en el mapa |
| B9 | Admin (#32–#34) | ML puede limpiar caché |
| B10 | F2: `/compare`, `/zones` | — |

### Datos (Diego)

- Llenar `strategy_effects.reduction_pct_*` y `adaptation_strategies.cost_usd_ha_year` con literatura/INIAP.
- Llenar `areas` (cantones de la Costa), `enso_index`, `area_scenario_climate`, `disease_risk_*`,
  `crop_suitability`, `crop_exposure`, `crop_prices`.
- Resolver I3, I5, I9.

### ML

- Checklist de [03-integracion-ml.md](03-integracion-ml.md) § 6.

### Front

- Consumir [02-endpoints.md](02-endpoints.md); empezar con `USE_MOCKS=true`.
- Capas raster NASA (NDVI MODIS, lluvia IMERG) directo de **GIBS WMTS** (sin key):
  `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{Layer}/default/{Time}/GoogleMapsCompatible_Level{N}/{z}/{y}/{x}.png`
