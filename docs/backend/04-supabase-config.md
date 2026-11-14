# 4. Supabase y configuración

Esquema: [`supabase/migrations/`](../../supabase/migrations) (0001–0005, de Datos).
Detalle de tablas: [docs/02-base-de-datos.md](../02-base-de-datos.md).

## 1. Tres clientes, tres usos

| Cliente | Clave | Para qué | Dónde |
|---------|-------|----------|-------|
| `anon_client()` | `SUPABASE_ANON_KEY` | **Todas las lecturas** (todo es lectura pública por RLS) | Repositorios |
| `user_client(jwt)` | anon + JWT del usuario | Escribir `field_observations`, `strategy_reviews` (RLS valida dueño) | Routers 🔒 |
| `service_client()` | `SUPABASE_SERVICE_ROLE_KEY` | Admin: `enso_index` refresh, validar JWT (`auth.get_user`) | Solo `admin.py`, `auth.py` |

Leer con `anon` (no con `service_role`) evita que un bug de la API exponga algo que RLS
protege (fincas privadas de `areas`).

```python
# app/core/supabase.py
from functools import lru_cache
from supabase import Client, create_client
from .config import settings

@lru_cache
def anon_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)

@lru_cache
def service_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)

def user_client(token: str) -> Client:
    c = create_client(settings.supabase_url, settings.supabase_anon_key)
    c.postgrest.auth(token)
    return c
```

## 2. Consultas por endpoint

`db = anon_client()`. Todas con `.execute().data`.

| Endpoint | Consulta |
|----------|----------|
| `/scenarios` | `db.table("scenarios").select("*").order("phase")` + `available` con `v_losses_active` `select("scenario_id")` distinct |
| `/crops/{c}/requirements` | `db.table("crop_requirements").select("*").eq("crop_id", c)` |
| `/crops/{c}/pathogens` | `db.table("pathogens").select("*, disease_thresholds(*)").eq("crop_id", c)` |
| `/enso/current` | `db.table("enso_index").select("*").eq("index_id","oni").order("month_date", desc=True).limit(1)` (ídem `nino12_anom`) + `enso_events` con `end_month is null` |
| `/enso/history` | `.in_("index_id", [...]).gte("month_date", f).lte("month_date", t).order("month_date")` |
| `/areas` | provincia por nombre → `id`; luego `db.table("areas").select("id,name,kind,area_ha,parent_id").eq("kind", k).eq("parent_id", pid)` |
| `/areas/geojson` | `db.rpc("areas_geojson", {"p_kind": k, "p_parent": pid, "p_tolerance": tol})` |
| `/areas/lookup` | `db.rpc("area_at_point", {"p_lat": lat, "p_lon": lon})` |
| `/areas/{id}/climate` | `db.table("area_scenario_climate").select("*").eq("area_id", id).eq("scenario_id", s).in_("variable_id", vs)` |
| `/areas/{id}/series` | `db.table("area_monthly_series")…gte/lte("month_date")` — **paginar** (PostgREST corta en 1000 filas) |
| `/areas/{id}/risk` | `db.table("disease_risk_scenario").select("*").eq("area_id", id).eq("scenario_id", s)` |
| `/losses` | `db.table("v_losses_active").select("*").eq("crop_id", c).eq("scenario_id", s).eq("area_kind", k)[.eq("parent_id", pid)]` |
| `/areas/{id}/strategies` | `db.table("strategy_evaluations").select("*, adaptation_strategies(*)").eq("prediction_id", pred_id).order("rank")` |
| `/zones` | `db.table("zone_classification").select("*, areas(name)").eq("future_scenario_id", f)` |
| `/meta` | `data_sources`, `variables`, `model_versions` `.eq("is_active", True)` |

> **Límite de 1000 filas:** PostgREST devuelve máx. 1000 por defecto. Para series largas usar
> `.range(i, i+999)` en bucle (helper `fetch_all()` en `repositories/_base.py`).

## 3. Lo que aporta la `0006_revision.sql` de Datos (ya desplegada)

El backend **no crea ni modifica nada en la BD**. Usa lo que ya existe:

| Necesidad de la API | Cómo se resuelve |
|---------------------|------------------|
| GeoJSON del mapa | `areas.geom_simplified` (generada, ~200 m). PostgREST la devuelve como GeoJSON; si llega como WKB hex, el backend la decodifica con `shapely`. |
| ¿En qué cantón cae un punto? | El backend carga `geom_simplified` de los cantones (caché 24 h) y usa `shapely` (`contains`). Sin RPC. |
| Pérdidas del modelo activo con nombres | Vista `v_loss_map` (una fila por área × escenario). |
| Buscar provincia por nombre sin tildes | `areas.name_key` (minúsculas, sin tildes). |
| Ventana de riesgo del cultivo | `crop_phenology` (`is_risk_window`). |
| Clasificación Niño/Niña/neutral por año | Vista `v_enso_year_class`. |
| Efecto de cada estrategia | `strategy_effects` (si `reduction_pct_*` está vacío, el backend usa valores por defecto marcados *por validar*). |
| Peligros climáticos mensuales | `area_monthly_hazard`. |

Lo que **no** hay y el backend compensa sin tocar la BD:

- `loss_predictions` no guarda el vector de features → el what-if lo reconstruye
  (`bundle["scenario_features"]` del modelo, o desde `disease_risk_scenario` +
  `area_scenario_climate`). Ver [03](03-integracion-ml.md).
- `strategy_evaluations` → el backend calcula las estrategias **al vuelo** (no escribe la tabla).

## 4. MCP de Supabase (para trabajar con la BD desde Claude Code)

Opción recomendada, **servidor remoto oficial** (login OAuth en el navegador, sin pegar tokens):

```bash
claude mcp add --scope project --transport http supabase \
  "https://mcp.supabase.com/mcp?project_ref=<PROJECT_REF>&read_only=true"
```

- `project_ref`: limita el MCP a **este** proyecto (Settings → General → Reference ID).
- `read_only=true`: puede consultar y ver esquema, no modificar. Quitarlo solo para aplicar
  migraciones, y volver a ponerlo.
- No conectar a un proyecto con datos reales de usuarios.

Alternativa local (requiere *personal access token*, que **cada uno** pone en su máquina):

```bash
claude mcp add --scope local supabase -e SUPABASE_ACCESS_TOKEN=<token> -- \
  npx -y @supabase/mcp-server-supabase@latest --project-ref=<PROJECT_REF> --read-only
```

## 5. Variables de entorno (`BACK/.env`)

```env
# ── Supabase ──────────────────────────────────────────
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=               # pública (la misma del front)
SUPABASE_SERVICE_ROLE_KEY=       # SECRETA — solo backend
ADMIN_EMAILS=                    # emails admin separados por coma
ADMIN_API_KEY=                   # cabecera X-Admin-Key para scripts (ETL/ML)

# ── Modelo ────────────────────────────────────────────
PREDICTOR_MODE=local             # local | remote | off
ML_SERVICE_URL=                  # solo si PREDICTOR_MODE=remote
MODEL_CACHE_DIR=.model_cache     # donde se descarga el .joblib

# ── API ───────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000
USE_MOCKS=false                  # true = responde con app/mocks/*.json
CACHE_TTL_SECONDS=3600

# ── Fuentes externas (la API en vivo solo usa POWER y NOAA, sin key) ──
NASA_POWER_URL=https://power.larc.nasa.gov/api
# GEE_PROJECT / EARTHDATA_* los usa el ETL, no la API
```

| Variable | Dónde se obtiene |
|----------|------------------|
| `SUPABASE_*` | Supabase → Project Settings → API |
| `ADMIN_API_KEY` | Inventada por el equipo: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `EARTHDATA_TOKEN` (ETL, Fase 3) | https://urs.earthdata.nasa.gov → Generate Token (60 días) + aprobar apps (LP DAAC, AppEEARS) |

> Si se filtra la `service_role`: Supabase → API → *Roll key*.

## 6. Dependencias (`BACK/requirements.txt`)

```
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.8
pydantic-settings>=2.4
supabase>=2.10,<3
httpx>=0.27
cachetools>=5.3
python-dotenv>=1.0
# what-if (misma versión que ml/requirements.txt)
joblib>=1.4
scikit-learn==1.5.2
numpy>=1.26
pandas>=2.2
```

## 7. Cómo correr (Linux / macOS)

```bash
cd BACK
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # rellenar
uvicorn run:app --reload --host 0.0.0.0 --port 8000
# http://localhost:8000/docs  ·  http://localhost:8000/health
```

Windows: `py -3.12 -m venv venv` y `venv\Scripts\activate`.
