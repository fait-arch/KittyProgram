# 4. Supabase y configuración

Esquema: [`supabase/migrations/`](../../supabase/migrations) (0001–0005, de Datos).
Detalle de tablas: [docs/02-base-de-datos.md](../02-base-de-datos.md).

Proyecto: **`chjgktgkilxjuwuuekah`** → `SUPABASE_URL=https://chjgktgkilxjuwuuekah.supabase.co`

## 1. Dos clientes

| Cliente | Clave | Para qué |
|---------|-------|----------|
| `anon_client()` | `SUPABASE_ANON_KEY` | **Todas las lecturas** (todo es lectura pública por RLS) y validar JWT (`auth.get_user`) |
| `user_client(jwt)` | anon + JWT del usuario | Escribir `field_observations` (RLS valida que sea suyo) |

La API prefiere la **publishable**: no escribe en el esquema y así un bug no puede saltarse RLS.
Si solo hay `SUPABASE_SECRET_KEY`, la usa para leer (con aviso en logs y en `/health`).
Código: `BACK/app/core/supabase.py`, consultas en `BACK/app/data/supabase_source.py`.

## 2. Consultas por endpoint

`db = anon_client()`. Todas con `.execute().data`.

| Endpoint | Consulta |
|----------|----------|
| `/scenarios` | `db.table("scenarios").select("*").order("phase")` + `available` con `v_loss_map` `select("scenario_id")` |
| `/crops/{c}/requirements` | `db.table("crop_requirements").select("*").eq("crop_id", c)` |
| `/crops/{c}/pathogens` | `db.table("pathogens").select("*, disease_thresholds(*)").eq("crop_id", c)` |
| `/enso/current` | `db.table("enso_index").select("*").eq("index_id","oni").order("month_date", desc=True).limit(1)` (ídem `nino12_anom`) + `enso_events` con `end_month is null` |
| `/enso/history` | `.in_("index_id", [...]).gte("month_date", f).lte("month_date", t).order("month_date")` |
| `/areas` | provincia por nombre → `id`; luego `db.table("areas").select("id,name,kind,area_ha,parent_id").eq("kind", k).eq("parent_id", pid)` |
| `/areas/geojson` | `db.table("areas").select("id,name,kind,parent_id,region,geom_simplified").eq("kind", k)` |
| `/areas/lookup` | geometrías de cantones en caché + `shapely` `STRtree` |
| `/areas/{id}/climate` | `db.table("area_scenario_climate").select("*").eq("area_id", id).eq("scenario_id", s).in_("variable_id", vs)` |
| `/areas/{id}/series` | `db.table("area_monthly_series")…gte/lte("month_date")` — **paginar** (PostgREST corta en 1000 filas) |
| `/areas/{id}/risk` | `db.table("disease_risk_scenario").select("*").eq("area_id", id).eq("scenario_id", s)` |
| `/losses` | `db.table("v_loss_map").select(<sin geom>).eq("crop_id", c).eq("scenario_id", s).eq("kind", k)[.eq("province", nombre)]` |
| `/areas/{id}/strategies` | `loss_predictions` (modelo activo) + `disease_risk_scenario` + `strategy_effects` + `adaptation_strategies` |
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
  "https://mcp.supabase.com/mcp?project_ref=chjgktgkilxjuwuuekah&read_only=true"
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

## 5. Variables de entorno (`BACK/.env`, plantilla en `BACK/.env.example`)

| Variable | Defecto | Para qué |
|----------|---------|----------|
| `DATA_SOURCE` | `mock` | `mock` (datos sintéticos) o `supabase` |
| `SUPABASE_URL` | — | `https://<project-ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | — | Publishable (`sb_publishable_…`) o anon. **Recomendada** |
| `SUPABASE_SECRET_KEY` | — | `sb_secret_…`: salta RLS. Solo respaldo de lectura si falta la publishable; `/health` avisa `key_type: secret` |
| `AI_PROVIDER` | `deepseek` | `deepseek` o `anthropic` |
| `DEEPSEEK_API_KEY` | — | Insights IA. Sin ella, `/insights` y `/ask` → `503 ai_not_configured` |
| `ANTHROPIC_API_KEY` | — | Solo si `AI_PROVIDER=anthropic` |
| `AI_MODEL` | vacío | `deepseek-chat` / `claude-opus-5-5` por defecto |
| `ML_INFERENCE_MODULE` | `ml.inference` | Módulo opcional de ML (raíz del repo) |
| `PREDICTOR_MODE` / `MODEL_PATH` | `local` / `models/cacao_loss.joblib` | Modelo ML dentro del backend |
| `ADMIN_API_KEY` | — | Cabecera `X-Admin-Key` para `/admin/*` |
| `ADMIN_EMAILS` | — | Alternativa: JWT de estos emails |
| `CORS_ORIGINS` | `http://localhost:3000` | Orígenes del front (separados por coma) |
| `CACHE_TTL_SECONDS` | `3600` | Caché de lecturas |

NASA POWER y NOAA CPC **no necesitan key**. GEE y Earthdata solo los usa el ETL.

> Si se filtra una clave: Supabase → API → *Roll key*; Anthropic → Console → revocar la key.

## 6. Cómo correr

```bash
cd BACK
uv venv --python 3.12 venv          # o: python3.12 -m venv venv
uv pip install --python venv/bin/python -r requirements.txt   # o: venv/bin/pip install -r requirements.txt
cp .env.example .env                 # rellenar
venv/bin/uvicorn run:app --reload --host 0.0.0.0 --port 8000
# Swagger: http://localhost:8000/docs   ·   Salud: http://localhost:8000/health
venv/bin/python -m pytest -q         # 50 tests, modo mock, sin red ni claves
```

Windows: `py -3.12 -m venv venv` y `venv\Scripts\...`.

Para pasar a datos reales: `DATA_SOURCE=supabase` + `SUPABASE_URL` + `SUPABASE_ANON_KEY`, y
`POST /api/v1/admin/cache/clear` cuando ETL/ML carguen datos nuevos.
