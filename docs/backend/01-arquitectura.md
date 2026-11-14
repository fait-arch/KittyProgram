# 1. Arquitectura del backend integrador

## Quién hace qué

| Pieza | Dueño | Escribe en | El backend… |
|-------|-------|------------|-------------|
| **ETL** (GEE, NOAA, ESPAC, SIPA, POWER) | Datos | `areas`, `area_monthly_series`, `area_scenario_climate`, `disease_risk_*`, `crop_suitability`, `crop_production_stats`, `crop_exposure`, `crop_prices`, `enso_*` | Solo **lee** |
| **Modelo** (`ml/train.py`, `ml/predict.py`) | ML | `model_versions`, `training_samples`, `loss_predictions`, artefacto `.joblib` en Storage | **Lee** predicciones y **carga** el artefacto para el what-if |
| **Estrategias** (`ml/strategies.py` o backend) | Backend (decisión abierta, ver [05](05-pendientes.md)) | `strategy_evaluations`, `zone_classification` | Lee; reordena según prioridades del agricultor |
| **API FastAPI** | Backend | `field_observations`, `strategy_reviews` (como el usuario) | Expone todo al front |
| **Frontend** | Front | — | Consume `/api/v1` |

## Capas dentro de `BACK/app`

```
BACK/
├── run.py                      # app = create_app()
├── requirements.txt
├── .env.example
└── app/
    ├── main.py                 # create_app(): CORS, routers, handlers de error, lifespan
    ├── core/
    │   ├── config.py           # Settings (pydantic-settings) desde .env
    │   ├── supabase.py         # anon_client() · service_client() · user_client(token)
    │   ├── auth.py             # get_current_user (JWT Supabase), require_admin
    │   ├── cache.py            # TTLCache en memoria por clave de consulta
    │   └── errors.py           # PostgREST → HTTP
    ├── schemas/                # Pydantic de respuesta (el contrato de 02-endpoints.md)
    │   ├── common.py           # Disclaimer, ModelInfo, Paginated
    │   ├── catalog.py · enso.py · areas.py · losses.py · strategies.py · predict.py
    ├── repositories/           # SOLO consultas a Supabase, una función por consulta
    │   ├── catalog_repo.py · enso_repo.py · areas_repo.py · climate_repo.py
    │   ├── risk_repo.py · losses_repo.py · strategies_repo.py · model_repo.py
    ├── services/               # lógica: agregar, combinar, reordenar
    │   ├── detail_service.py   # arma /areas/{id}/detail (varias tablas → 1 respuesta)
    │   ├── strategy_service.py # reordena estrategias por prioridades del agricultor
    │   ├── predictor.py        # carga el modelo activo y hace what-if
    │   ├── power_service.py    # proxy NASA POWER con caché
    │   └── enso_service.py     # fase ENSO actual + refresco NOAA
    ├── routers/                # HTTP: validar params, llamar service/repo, devolver schema
    │   ├── system.py · catalog.py · enso.py · areas.py · losses.py
    │   ├── strategies.py · predict.py · point.py · field.py · admin.py
    └── mocks/                  # JSON de ejemplo con el formato real (USE_MOCKS=true)
```

> Endpoints con `def` (no `async def`): `supabase-py` es síncrono y FastAPI los corre en un
> *thread pool*. Para `httpx` (POWER) se usa el cliente síncrono también, para no mezclar.

## Qué es precalculado y qué es en vivo

| Respuesta | Origen | Latencia esperada |
|-----------|--------|-------------------|
| Mapa de pérdidas, detalle, estrategias, riesgo, aptitud | Supabase (precalculado) | < 200 ms (con caché < 5 ms) |
| GeoJSON de cantones | RPC PostGIS simplificada | < 500 ms primera vez, luego caché |
| ENSO actual | Supabase (`enso_index`); refresco NOAA por `/admin` | < 100 ms |
| Clima de un punto cualquiera | NASA POWER en vivo | 1–5 s primera vez, luego caché 24 h |
| What-if (sliders de lluvia/temperatura/Niño) | Modelo en memoria | < 50 ms |
| Capas raster (NDVI, lluvia) en el mapa | **El front pide directo a NASA GIBS (WMTS, sin key)** | — |

## Caché

- **En memoria** (`cachetools.TTLCache`), clave = ruta + parámetros normalizados.
  - Catálogos, escenarios, GeoJSON: TTL 24 h.
  - Pérdidas/detalle/estrategias: TTL 1 h (cambian solo cuando ML vuelve a predecir).
  - POWER por punto: TTL 24 h, coordenadas redondeadas a 2 decimales (~1 km).
- **Invalidación:** `POST /api/v1/admin/cache/clear` (lo llama el ML al terminar `predict.py`).
- Cabecera `Cache-Control: public, max-age=300` en respuestas de lectura.

## Flujo de una petición típica: clic en un cantón

```
GET /api/v1/areas/{id}/detail?scenario=nino&crop=cacao
  └─ detail_service.build(area_id, crop, scenario)
       ├─ areas_repo.get(area_id)                     → areas + padre (provincia)
       ├─ losses_repo.get(area, crop, scenario)       → loss_predictions (modelo activo)
       ├─ losses_repo.get(area, crop, "normal")       → para "vs año normal"
       ├─ risk_repo.monthly(area, scenario)           → disease_risk_scenario (12 × patógeno)
       ├─ climate_repo.scenario(area, scenario)       → area_scenario_climate
       ├─ catalog_repo.requirements(crop)             → crop_requirements
       ├─ risk_repo.suitability(area, crop, scenario) → crop_suitability
       └─ model_repo.active(crop)                     → model_versions
  → 1 JSON listo para pintar el panel (no obliga al front a hacer 7 llamadas)
```

## Errores

| Código | Cuándo |
|--------|--------|
| `400` | Parámetro válido en tipo pero inválido en contenido (escenario inexistente, etc.) |
| `401` / `403` | Falta token / no es admin |
| `404` | Área, cultivo o predicción no existe |
| `409` | Unicidad (observación repetida) |
| `422` | Validación Pydantic |
| `503` | Supabase caído, modelo no cargado (solo `/predict`), POWER no responde |

Forma: `{"detail": "mensaje", "code": "loss_not_found"}` — `code` estable para el front.
