# 2. Configuración

## Requisitos

- **Python 3.12** (con 3.14, `pydantic==2.8.2` no tiene wheels y la instalación falla).
- Cuenta de **Google Earth Engine** con un proyecto de Google Cloud registrado (uso no comercial).
- Proyecto de **Supabase**.
- (Opcional) Cuenta de **NASA Earthdata** para ECOSTRESS.
- NASA POWER no necesita cuenta.

## Variables de entorno (`BACK/.env`)

```env
# ── Google Earth Engine ──────────────────────────
GEE_PROJECT=tu-project-id
# Producción / Docker (opcional):
# GEE_SERVICE_ACCOUNT=gee-backend@tu-project-id.iam.gserviceaccount.com
# GEE_PRIVATE_KEY_PATH=/app/gee-key.json

# ── Supabase ─────────────────────────────────────
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=...             # pública, la misma del frontend
SUPABASE_SERVICE_ROLE_KEY=...     # SECRETA: solo backend

# ── NASA Earthdata (opcional) ────────────────────
EARTHDATA_TOKEN=...               # caduca a los 60 días
```

> ⚠️ `.env` está en `.gitignore`. **Nunca** subir la `service_role key` ni el token de Earthdata.
> Si se filtran: Supabase → *Project Settings → API → Roll key*; Earthdata → *Revoke token*.

### Dónde obtener cada valor

| Variable | Dónde |
|----------|-------|
| `GEE_PROJECT` | https://code.earthengine.google.com/register → ID del proyecto Cloud |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase → *Project Settings → API* |
| `EARTHDATA_TOKEN` | https://urs.earthdata.nasa.gov → *Generate Token* |

## Instalación

```bash
cd BACK
py -3.12 -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install supabase earthaccess     # nuevas dependencias del CRUD
venv\Scripts\earthengine authenticate             # una vez por máquina
```

Añadir a `requirements.txt`:

```
supabase>=2.10,<3
earthaccess>=0.12
```

## Ejecutar

```bash
venv\Scripts\python -m uvicorn run:app --reload --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` es necesario para que el frontend acceda por IP de red (y desde el móvil).
- El frontend llama a `http://<hostname>:8000`. Si otro programa ocupa `127.0.0.1:8000`,
  abrir el frontend por la IP de red, no por `localhost`.

## Comprobación

```bash
curl http://localhost:8000/health
# {"status":"ok","gee_ready":true,"gee_error":null}
```

Si `gee_ready` es `false`, el backend arranca en **modo degradado**: los endpoints que usan GEE
responden `503` con el motivo. El CRUD de Supabase sigue funcionando.

## Migraciones de base de datos

Los archivos están en `supabase/migrations/` (raíz del repo) y se aplican en orden:

| Archivo | Contenido |
|---------|-----------|
| `0001_init.sql` | 13 tablas, PostGIS, RLS, semilla de fuentes y variables NASA |
| `0002_fk_indexes.sql` | Índices para claves foráneas |
| `0003_field_rpc.sql` | RPC `create_field` y `update_field_geom` (GeoJSON → PostGIS) |

Para aplicarlas en un proyecto nuevo: pegarlas en *SQL Editor* de Supabase en ese orden,
o usar la CLI: `supabase db push`.
