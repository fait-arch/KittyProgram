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
├── run.py                      # app = create_app()  →  uvicorn run:app
├── requirements.txt · .env.example
├── models/                     # aquí ML deja cacao_loss.joblib (no se versiona)
├── tests/                      # pytest: contrato en modo mock, IA simulada, bundles sklearn reales
└── app/
    ├── main.py                 # create_app(): CORS, routers, errores, /health, cabecera X-Data-Source
    ├── core/
    │   ├── config.py           # Settings (pydantic-settings) desde BACK/.env
    │   ├── supabase.py         # anon_client() · user_client(jwt)
    │   ├── auth.py             # get_current_user (JWT Supabase), require_admin (X-Admin-Key)
    │   ├── cache.py            # @cached(ttl): TTLCache en memoria + clear_all()
    │   └── errors.py           # ApiError(status, code, detail) → {"detail","code"}
    ├── data/                   # ÚNICO lugar que sabe de dónde vienen los datos
    │   ├── supabase_source.py  # lecturas PostgREST (paginadas), usa v_loss_map, geom_simplified…
    │   ├── mock_source.py      # misma interfaz, datos sintéticos (DATA_SOURCE=mock)
    │   └── common.py           # name_key (sin tildes), GeoJSON/WKB, uuid
    ├── services/               # lógica: no saben si la fuente es mock o Supabase
    │   ├── territory.py        # provincias, GeoJSON, lookup por punto (shapely STRtree)
    │   ├── enso.py             # fase actual; NOAA CPC en vivo si la BD está vacía
    │   ├── climate.py          # climatología, ventana de riesgo, riesgo por patógeno, chequeo ECOCROP
    │   ├── losses.py           # mapa, resumen, fila completa del modelo activo
    │   ├── detail.py           # panel del cantón (una llamada)
    │   ├── strategies.py       # evaluación al vuelo + ranking por prioridades (+ supuestos por validar)
    │   ├── predictor.py        # carga el .joblib y hace el what-if
    │   ├── insights.py         # IA: insights estructurados y preguntas libres
    │   ├── ai_providers.py     # DeepSeek (por defecto) o Claude, misma interfaz
    │   ├── power.py            # NASA POWER por punto (caché 24 h)
    │   └── labels.py           # textos para agricultor, disclaimer, atribución, etiquetas de features
    └── routers/                # HTTP: catalog · enso · areas · losses · advice · misc
```

> Endpoints con `def` (no `async def`): `supabase-py` y el SDK de Anthropic se usan en modo
> síncrono y FastAPI los corre en un *thread pool*.

## Qué es precalculado y qué es en vivo

| Respuesta | Origen | Latencia esperada |
|-----------|--------|-------------------|
| Mapa de pérdidas, detalle, estrategias, riesgo, aptitud | Supabase (precalculado) | < 200 ms (con caché < 5 ms) |
| GeoJSON de cantones | RPC PostGIS simplificada | < 500 ms primera vez, luego caché |
| ENSO actual | Supabase (`enso_index`); refresco NOAA por `/admin` | < 100 ms |
| Clima de un punto cualquiera | NASA POWER en vivo | 1–5 s primera vez, luego caché 24 h |
| Estrategias | Calculadas al vuelo (pérdida × efectos) | < 50 ms |
| Insights IA | DeepSeek / Claude (JSON validado) | 10–40 s primera vez, luego caché 6 h |
| What-if (sliders de lluvia/temperatura/Niño) | Modelo en memoria | < 50 ms |
| Capas raster (NDVI, lluvia) en el mapa | **El front pide directo a NASA GIBS (WMTS, sin key)** | — |

## Caché

- **En memoria** (`cachetools.TTLCache`), clave = ruta + parámetros normalizados.
  - Catálogos, escenarios, GeoJSON: TTL 24 h.
  - Pérdidas/detalle/estrategias: TTL 1 h (cambian solo cuando ML vuelve a predecir).
  - POWER por punto: TTL 24 h, coordenadas redondeadas a 2 decimales (~1 km).
  - Insights IA: TTL 6 h por (área, escenario, prioridades).
- **Invalidación:** `POST /api/v1/admin/cache/clear` (llamarlo cuando ETL/ML actualicen la BD).
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
