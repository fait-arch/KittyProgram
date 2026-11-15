# 10 · Auditoría: front ↔ backend ↔ Supabase

Fecha: 14-nov-2026 · Rama `main` (c671d32 + cambios locales sin confirmar).
Fuentes revisadas: `BACK/app/routers/*`, `BACK/app/data/supabase_source.py`, `supabase/migrations/0001–0009`,
`supabase/seed/data/01–06`, `FRONT/src/lib/api/*` y las pantallas que los usan.

> **Límite de esta revisión:** no fue posible consultar la base real (`chjgktgkilxjuwuuekah`) desde el entorno de
> revisión, porque el proxy bloquea `*.supabase.co`. Los números de filas salen del **seed** del repositorio. Para
> medir la base real, corre `python tools/auditar_supabase.py` desde `BACK` (solo lectura; ver al final).

---

## 1. Cómo se conecta el backend

| Pieza | Estado |
|---|---|
| Fuente de datos | `BACK/.env` → `DATA_SOURCE=supabase` (antes `mock`). Se elige en `app/data/__init__.py`. |
| Cliente | `app/core/supabase.py` → `anon_client()` con la **publishable/anon key**; si no está, usa la **secret**. |
| Keys en `.env` | `SUPABASE_URL` ✔ · `SUPABASE_SECRET_KEY` ✔ · `SUPABASE_ANON_KEY` **vacía**. |
| Consecuencia | Las lecturas usan la clave secreta, que **salta RLS** (el backend lo avisa en el log). Funciona, pero conviene poner la publishable. |
| Escritura | `POST /observations` usa `user_client()`, que **exige** `SUPABASE_ANON_KEY` → hoy falla con 503. |
| Geometría | `areas.geom_simplified` es una columna **generada** (0006): se llena sola al cargar `areas`. |
| Pérdidas | Se leen de la vista `v_loss_map` (= `loss_predictions` del **modelo activo** + `areas`). El backend **no calcula** pérdidas al vuelo: si no hay fila para un escenario, ese escenario sale vacío. |
| Modelo ML | `PREDICTOR_MODE=local`, pero `BACK/models/` no tiene `.joblib`: solo funciona `POST /predict` sintético. No afecta al mapa. |

---

## 2. Endpoints: cuáles usa el front y cuáles no

Backend: **32 rutas** bajo `/api/v1`. El front usa **14**; además pide **1 que no existe** (`/export`).

### 2.1 Usados por el front

| Endpoint | Pantallas | Tablas / vistas en Supabase |
|---|---|---|
| `GET /meta` | Método y fuentes | `data_sources`, `variables`, `model_versions` |
| `GET /scenarios` | casi todas | `scenarios` (+ `v_loss_map` para `available`) |
| `GET /enso/current` | banner, Panel, Método, plantillas | `enso_index`, `enso_events` |
| `GET /areas` | buscador, Panel, Comparar, Plantillas | `areas`, `crop_exposure` |
| `GET /areas/geojson` | Mapa 2D, Comparar, Mi finca, plantillas | `areas.geom_simplified` |
| `GET /crops/cacao/requirements` | ficha del cantón, Mi finca | `crop_requirements` |
| `GET /losses` | Mapa, Panel, Comparar, Mi finca, plantillas | `v_loss_map` |
| `GET /losses/summary` | Panel, tarjeta resumen, gráfico de clases | `v_loss_map` |
| `GET /areas/{id}/detail` | ficha del cantón, Mi finca, plantillas, guardar sin conexión | `areas`, `area_static_features`, `v_loss_map`/`loss_predictions`, `disease_risk_scenario`, `area_scenario_climate`, `crop_suitability`, `crop_requirements` |
| `GET /areas/{id}/strategies` | ficha del cantón, plantillas | `adaptation_strategies`, `strategy_effects`, `crop_prices`, + lo del detalle |
| `GET /compare` | Comparar climas | `v_loss_map`, `crop_suitability`, `area_scenario_climate` |
| `GET /zones` | Mapa (Zonas 2050), Panel, Comparar | `zone_classification` |
| `GET /areas/lookup` | Mi finca | `areas.geom` (punto en polígono) |
| `GET /point/climate` | Mi finca | **NASA POWER en vivo** (no Supabase) |
| `GET /export` | Exportar a QGIS | **no existe en el backend** → el front arma la capa en el navegador |

### 2.2 No usados por el front (18)

| Endpoint | Qué da | Tablas | ¿Vale la pena conectarlo? |
|---|---|---|---|
| `GET /areas/{id}/insights` | Recomendaciones con IA (DeepSeek/Claude) | detalle + IA | **Sí** (Fase 6, asistente) |
| `POST /areas/{id}/ask` | Pregunta libre a la IA | detalle + IA | **Sí** (Fase 6) |
| `POST /predict` | What-if: lluvia/temperatura/Niño | modelo en memoria | Sí, cuando haya `.joblib` |
| `GET /areas/{id}/series` | Serie mensual observada + anomalía | `area_monthly_series` (84 546 filas) | **Sí**: el dato más grande y no se ve en ningún lado |
| `GET /areas/{id}/hazards` | Lluvia fuerte, humedad, saturación por mes | `area_monthly_hazard` (7 686) | **Sí**, para la ficha |
| `GET /areas/{id}/risk/history` | Riesgo observado mes a mes + ONI | `disease_risk_monthly` (23 058) | **Sí**: muestra cómo El Niño sube el riesgo |
| `GET /areas/{id}/risk` | Riesgo por mes y patógeno del escenario | `disease_risk_scenario` | Ya llega dentro de `/detail` |
| `GET /areas/{id}/climate` | Climatología del escenario | `area_scenario_climate` | Ya llega dentro de `/detail` |
| `GET /areas/{id}/suitability` | Aptitud ECOCROP por escenario | `crop_suitability` | Ya llega en `/detail` y `/compare` |
| `GET /areas/{id}` | Área sin geometría | `areas` | No hace falta |
| `GET /losses/geojson` | Mapa + pérdida en una sola llamada | `v_loss_map` | Opcional (ahorra una petición) |
| `GET /enso/history` | Series ONI / Niño 1+2 | `enso_index` (2 209) | **Sí**, para "¿Qué es El Niño?" |
| `GET /enso/events` | Eventos Niño/Niña | `enso_events` (24) | **Sí**, misma pantalla |
| `GET /enso/years` | Clase de cada año | `v_enso_year_class` | Sí, misma pantalla |
| `GET /crops` · `/crops/{c}/pathogens` · `/crops/{c}/phenology` | Catálogos del cultivo y su calendario | `crops`, `pathogens`, `disease_thresholds`, `crop_phenology` | Sí para Método (umbrales y ventana de riesgo) |
| `GET /strategies` | Catálogo de estrategias con supuestos | `adaptation_strategies`, `strategy_effects` | Opcional (Método) |
| `GET/POST /observations` | Observaciones de campo (GBIF, técnicos) | `field_observations` (12) | Fase 7; el POST requiere la anon key y login |
| `POST /admin/cache/clear` · `/admin/model/reload` | Administración | — | No (uso interno) |

---

## 3. Tablas de Supabase: qué tiene datos y qué falta

Filas según el seed del repo (lo cargado en Supabase puede diferir: verificar con el script).

| Tabla / vista | Filas (seed) | ¿La lee el backend? | Estado |
|---|---:|:-:|---|
| `areas` | 139 (1 país, 12 provincias, 126 cantones) | ✔ | Límites reales. **Falta Santa Elena** (el front tiene el filtro). |
| `area_static_features` | 138 | ✔ | Altitud, pendiente, suelo. |
| `scenarios`, `crops`, `crop_requirements`, `pathogens`, `disease_thresholds`, `crop_phenology`, `adaptation_strategies`, `strategy_effects`, `variables`, `data_sources` | catálogo (migraciones 0001–0006) | ✔ | Completos. |
| `enso_index` / `enso_events` | 2 209 / 24 | ✔ | Real (NOAA). |
| `area_monthly_series` | 84 546 | ✔ | Real (ERA5 vía Open-Meteo). **No se muestra en el front.** |
| `area_monthly_hazard` | 7 686 | ✔ | **No se muestra en el front.** |
| `disease_risk_monthly` | 23 058 | ✔ | **No se muestra en el front.** |
| `area_scenario_climate` | 5 832 | ✔ | Solo `normal`, `nino`, `nina` (nina parcial). **Faltan `actual`, `ssp245_2050`, `ssp585_2050`.** |
| `disease_risk_scenario` | 5 832 | ✔ | Igual: faltan `actual` y 2050. |
| `crop_suitability` | **12** | ✔ | Solo `normal` y solo 12 cantones. **Faltan 114 cantones y todos los demás escenarios.** |
| `crop_exposure` | 138 | ✔ | Hectáreas por cantón **sintéticas** (marcadas). |
| `crop_prices` | 309 | ✔ | Real (FRED/FAOSTAT). |
| `crop_production_stats` | 327 | ✘ | ESPAC 2023–25 real + 2001–22 sintético. Es para entrenar el modelo. |
| `model_versions` | 1 | ✔ | Modelo **demo sintético**, sin métricas → el front muestra "sin dato" en MAE. |
| `loss_predictions` → `v_loss_map` | 276 | ✔ | Solo `normal` y `nino` (138 cantones c/u), del modelo demo. **Faltan `actual`, `ssp245_2050`, `ssp585_2050`.** |
| `zone_classification` | **0** | ✔ | **Vacía** → Zonas 2050 sale vacío en Mapa, Panel y Comparar. |
| `field_observations` | 12 | ✔ | Pocas; el front no las usa. |
| `training_samples`, `strategy_evaluations`, `strategy_reviews`, `field_profiles` | 0 | ✘ | Sin uso hoy. |
| `etl_runs` | 1 | ✘ | Registro de cargas. |

### Qué verá el usuario con `DATA_SOURCE=supabase` y este seed

| Pantalla | Resultado |
|---|---|
| Mapa · Año normal / Año Niño | ✔ 126 cantones con límites reales (pérdidas del modelo **demo**). |
| Mapa · Actual, SSP2-4.5, SSP5-8.5 | ✘ **vacío**: no hay filas en `loss_predictions`. |
| Mapa · Zonas 2050 / Panel "zonas" | ✘ **vacío**: `zone_classification` sin filas. |
| Comparar climas | Parcial: normal y Niño sí; 2050 sin pérdida ni aptitud. |
| Ficha del cantón | Pérdida y riesgo sí; **aptitud vacía en 114 cantones**; factores del modelo demo. |
| Panel | Totales sí; reparto por clase solo para normal/Niño. |
| Método | Fuentes sí; métricas del modelo "sin dato". |
| Mi finca | Cantón sí (lookup); clima depende de NASA POWER en vivo. |

---

## 4. Lo que falta extraer o calcular (en orden de impacto)

1. **`loss_predictions` para `actual`, `ssp245_2050` y `ssp585_2050`** (y `nina` si se quiere mostrar).
   Requiere: modelo entrenado → predecir por cantón × escenario → insertar con el `model_version_id` activo.
2. **`zone_classification`** para `ssp245_2050` y `ssp585_2050`:
   `suitability_now` (normal) + `suitability_future` (2050) + `nino_risk` → `segura / manejo / transicion / critica`.
   Depende del punto 3.
3. **`crop_suitability`** para los 126 cantones × 6 escenarios (ECOCROP con `area_scenario_climate` + `area_static_features`).
4. **`area_scenario_climate` y `disease_risk_scenario`** para `actual` (ONI/Niño 1+2 vigentes sobre el clima normal) y 2050 (NEX-GDDP-CMIP6, método delta).
5. **Modelo real** (`model_versions` con métricas + `BACK/models/cacao_loss.joblib`): `training_samples` / `v_training_area_year` con ESPAC real.
6. **Exposición real** (`crop_exposure`): hectáreas de cacao por cantón (ESPAC/MAG/SIPA) en lugar de las sintéticas.
7. **Santa Elena** (provincia y cantones) en `areas`, o quitar el filtro del front.
8. **`SUPABASE_ANON_KEY`** (publishable) en `BACK/.env`: lecturas con RLS y habilita `POST /observations`.
9. **`GET /export`** en el backend (GeoPackage con estilo), o dejar la exportación en el navegador como está.

Guía de fuentes para cada dato: `docs/09-como-conseguir-los-datos-que-faltan.md`.

---

## 5. Verificar la base real

```bash
cd BACK
source venv/bin/activate
python tools/auditar_supabase.py
```

Muestra filas por tabla (marca las vacías) y una tabla de cobertura por escenario:
pérdida · aptitud · clima · riesgo, más las zonas 2050 y el modelo activo. Solo lectura; no imprime claves.
