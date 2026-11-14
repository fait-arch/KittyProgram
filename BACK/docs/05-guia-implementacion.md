# 5. Guía de implementación del CRUD

Patrón en 3 capas: **router → service → repository**. Cada recurso de
[04-api-crud.md](04-api-crud.md) sigue la misma receta.

## Estructura de carpetas

```
BACK/app/
├── main.py                    # registrar routers nuevos aquí
├── state.py
├── core/
│   ├── config.py              # lee variables de entorno
│   ├── supabase.py            # clientes: usuario (RLS) y servicio
│   ├── auth.py                # dependencia get_current_user
│   └── errors.py              # traduce errores de PostgREST a HTTP
├── models/
│   ├── schemas.py             # (existente)
│   ├── crops.py
│   ├── fields.py              # finca, perfil, prioridades, rotación
│   └── rotation.py            # corridas y estrategias
├── repositories/
│   ├── crops_repo.py
│   ├── fields_repo.py
│   ├── climate_repo.py        # caché NASA
│   └── rotation_repo.py
├── services/
│   ├── gee_service.py         # (existente)
│   ├── layers_service.py      # (existente)
│   ├── power_service.py       # NASA POWER
│   ├── climate_service.py     # orquesta caché + GEE/POWER
│   └── rotation_engine.py     # motor de puntuación
└── routers/
    ├── analysis.py · territory.py · chat.py   # (existentes)
    ├── crops.py
    ├── fields.py
    ├── areas.py
    ├── rotation.py
    └── reviews.py
```

> **Endpoints `def`, no `async def`.** `supabase-py` es síncrono; con `def` FastAPI los ejecuta
> en un thread pool y no bloquea el servidor.

---

## Paso 1 · Configuración — `core/config.py`

```python
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings:
    supabase_url: str = os.environ["SUPABASE_URL"]
    supabase_anon_key: str = os.environ["SUPABASE_ANON_KEY"]
    supabase_service_key: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    admin_emails: set[str] = {
        e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
    }

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

## Paso 2 · Clientes Supabase — `core/supabase.py`

```python
from functools import lru_cache
from supabase import Client, create_client
from .config import get_settings

@lru_cache
def service_client() -> Client:
    """Salta RLS. Solo para caché NASA, resultados y tareas de admin."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)

def user_client(access_token: str) -> Client:
    """Actúa como el usuario: RLS decide qué puede leer/escribir."""
    s = get_settings()
    client = create_client(s.supabase_url, s.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
```

## Paso 3 · Autenticación — `core/auth.py`

```python
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client
from .config import get_settings
from .supabase import service_client, user_client

bearer = HTTPBearer(auto_error=False)

@dataclass
class CurrentUser:
    id: str
    email: str | None
    token: str

    @property
    def db(self) -> Client:
        return user_client(self.token)

def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token")
    try:
        res = service_client().auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o caducado")
    if not res or not res.user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o caducado")
    return CurrentUser(id=res.user.id, email=res.user.email, token=creds.credentials)

def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if (user.email or "").lower() not in get_settings().admin_emails:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
    return user
```

## Paso 4 · Errores — `core/errors.py`

```python
from fastapi import HTTPException
from postgrest.exceptions import APIError

PG_TO_HTTP = {
    "23505": (409, "Ya existe un registro con esos datos"),
    "23503": (409, "Referencia inválida o registro en uso"),
    "23514": (400, "Valor fuera de rango"),
    "22P02": (400, "Formato inválido"),
    "42501": (404, "No encontrado"),     # RLS: no se revela si existe
    "XX000": (400, "Geometría inválida"),
}

def raise_http(e: APIError) -> None:
    code, msg = PG_TO_HTTP.get(e.code or "", (500, "Error de base de datos"))
    raise HTTPException(code, f"{msg}: {e.message}" if code != 404 else msg)
```

---

## Paso 5 · Ejemplo completo: CRUD de cultivos

### Modelos — `models/crops.py`

```python
from typing import Literal
from pydantic import BaseModel, Field

CropType = Literal["cash", "staple", "legume", "cover", "perennial", "forage"]

class CropBase(BaseModel):
    name_es: str
    scientific_name: str | None = None
    family: str
    crop_type: CropType
    region: list[Literal["costa", "sierra", "amazonia"]] = []
    cycle_days: int | None = Field(None, gt=0)
    is_perennial: bool = False
    temp_opt_min_c: float | None = None
    temp_opt_max_c: float | None = None
    rain_min_mm_cycle: float | None = None
    rain_max_mm_cycle: float | None = None
    altitude_max_m: float | None = None
    kc_ini: float | None = None
    kc_mid: float | None = None
    kc_end: float | None = None
    n_fixing: bool = False
    n_fix_kg_ha: float | None = None
    residue_t_ha: float | None = None
    ground_cover: float | None = Field(None, ge=0, le=1)
    drought_tolerance: int | None = Field(None, ge=1, le=5)
    waterlog_tolerance: int | None = Field(None, ge=1, le=5)
    price_usd_t: float | None = None
    source_ref: str | None = None

class CropCreate(CropBase):
    id: str = Field(pattern=r"^[a-z0-9_]+$")

class CropUpdate(BaseModel):                    # todos opcionales para PATCH
    model_config = {"extra": "forbid"}
    name_es: str | None = None
    price_usd_t: float | None = None
    # … resto de campos de CropBase como opcionales

class Crop(CropCreate):
    pass
```

### Repositorio — `repositories/crops_repo.py`

```python
from postgrest.exceptions import APIError
from supabase import Client
from ..core.errors import raise_http

TABLE = "crops"

def list_crops(db: Client, region: str | None, crop_type: str | None, n_fixing: bool | None):
    q = db.table(TABLE).select("*").order("name_es")
    if region:
        q = q.contains("region", [region])
    if crop_type:
        q = q.eq("crop_type", crop_type)
    if n_fixing is not None:
        q = q.eq("n_fixing", n_fixing)
    return q.execute().data

def get_crop(db: Client, crop_id: str):
    res = db.table(TABLE).select("*").eq("id", crop_id).limit(1).execute()
    return res.data[0] if res.data else None

def create_crop(db: Client, data: dict):
    try:
        return db.table(TABLE).insert(data).execute().data[0]
    except APIError as e:
        raise_http(e)

def update_crop(db: Client, crop_id: str, data: dict):
    try:
        res = db.table(TABLE).update(data).eq("id", crop_id).execute()
        return res.data[0] if res.data else None
    except APIError as e:
        raise_http(e)

def delete_crop(db: Client, crop_id: str) -> bool:
    try:
        res = db.table(TABLE).delete().eq("id", crop_id).execute()
        return bool(res.data)
    except APIError as e:
        raise_http(e)
```

### Router — `routers/crops.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from ..core.auth import CurrentUser, require_admin
from ..core.supabase import service_client
from ..models.crops import Crop, CropCreate, CropUpdate
from ..repositories import crops_repo

router = APIRouter()

@router.get("", response_model=list[Crop])
def list_crops(region: str | None = None, crop_type: str | None = None,
               n_fixing: bool | None = Query(None)):
    return crops_repo.list_crops(service_client(), region, crop_type, n_fixing)

@router.get("/{crop_id}", response_model=Crop)
def get_crop(crop_id: str):
    crop = crops_repo.get_crop(service_client(), crop_id)
    if not crop:
        raise HTTPException(404, "Cultivo no encontrado")
    return crop

@router.post("", response_model=Crop, status_code=status.HTTP_201_CREATED)
def create_crop(body: CropCreate, _: CurrentUser = Depends(require_admin)):
    return crops_repo.create_crop(service_client(), body.model_dump(exclude_none=True))

@router.patch("/{crop_id}", response_model=Crop)
def update_crop(crop_id: str, body: CropUpdate, _: CurrentUser = Depends(require_admin)):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "Nada que actualizar")
    crop = crops_repo.update_crop(service_client(), crop_id, data)
    if not crop:
        raise HTTPException(404, "Cultivo no encontrado")
    return crop

@router.delete("/{crop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crop(crop_id: str, _: CurrentUser = Depends(require_admin)):
    if not crops_repo.delete_crop(service_client(), crop_id):
        raise HTTPException(404, "Cultivo no encontrado")
    return Response(status_code=204)
```

### Registrar — `main.py`

```python
from .routers import crops, fields, areas, rotation, reviews

app.include_router(crops.router,    prefix="/api/v1/crops",  tags=["Crops"])
app.include_router(fields.router,   prefix="/api/v1/fields", tags=["Fields"])
app.include_router(areas.router,    prefix="/api/v1",        tags=["Areas & NASA data"])
app.include_router(rotation.router, prefix="/api/v1",        tags=["Rotation"])
app.include_router(reviews.router,  prefix="/api/v1",        tags=["Reviews"])
```

---

## Paso 6 · Fincas (datos del usuario → cliente con RLS)

Diferencias con cultivos:

1. Se usa **`user.db`** (cliente del usuario) → RLS garantiza que solo vea/edite lo suyo.
   No hace falta filtrar por `owner_id` a mano.
2. Crear y cambiar geometría va por **RPC** (PostgREST no convierte GeoJSON a `geometry`).
3. Al leer, PostgREST devuelve la columna `geom` como GeoJSON (PostGIS 3; verificado:
   `to_json(geom)` → `{"type":"MultiPolygon","crs":…,"coordinates":…}`). Leaflet ignora `crs`.

```python
# repositories/fields_repo.py
FIELD_COLS = "id,kind,name,parent_id,area_ha,created_at"

def list_fields(db, with_geom: bool):
    cols = FIELD_COLS + (",geom" if with_geom else "")
    return db.table("areas").select(cols).eq("kind", "field").order("created_at").execute().data

def create_field(db, name: str, geojson: dict, parent_id: str | None):
    res = db.rpc("create_field", {"p_name": name, "p_geojson": geojson,
                                  "p_parent": parent_id}).execute()
    return res.data

def get_field_full(db, field_id: str):
    res = (db.table("areas")
             .select(f"{FIELD_COLS},geom,"
                     "field_profiles(*),field_priorities(*),"
                     "field_current_rotation(position,crop_id,start_month,months)")
             .eq("id", field_id).eq("kind", "field").limit(1).execute())
    return res.data[0] if res.data else None

def rename_field(db, field_id: str, name: str):
    res = db.table("areas").update({"name": name}).eq("id", field_id).execute()
    return res.data[0] if res.data else None

def update_geom(db, field_id: str, geojson: dict):
    return db.rpc("update_field_geom", {"p_id": field_id, "p_geojson": geojson}).execute().data

def delete_field(db, field_id: str) -> bool:
    return bool(db.table("areas").delete().eq("id", field_id).execute().data)

# Perfil / prioridades: upsert por area_id
def upsert_one_to_one(db, table: str, field_id: str, data: dict):
    return db.table(table).upsert({"area_id": field_id, **data}).execute().data[0]

# Rotación: reemplazo completo
def replace_rotation(db, field_id: str, items: list[dict]):
    db.table("field_current_rotation").delete().eq("area_id", field_id).execute()
    rows = [{"area_id": field_id, "position": i, **it} for i, it in enumerate(items)]
    return db.table("field_current_rotation").insert(rows).execute().data if rows else []
```

```python
# routers/fields.py (extracto)
@router.post("", status_code=201)
def create_field(body: FieldCreate, user: CurrentUser = Depends(get_current_user)):
    try:
        return fields_repo.create_field(user.db, body.name,
                                        body.geometry.model_dump(), body.canton_id)
    except APIError as e:
        raise_http(e)

@router.put("/{field_id}/priorities")
def put_priorities(field_id: str, body: Priorities,
                   user: CurrentUser = Depends(get_current_user)):
    try:
        return fields_repo.upsert_one_to_one(user.db, "field_priorities",
                                             field_id, body.model_dump())
    except APIError as e:
        raise_http(e)     # si la finca no es suya → RLS → 404
```

Validación del GeoJSON en el modelo:

```python
# models/fields.py
from pydantic import BaseModel, field_validator

class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list

    @field_validator("coordinates")
    @classmethod
    def inside_ecuador(cls, v, info):
        def points(c):
            if c and isinstance(c[0], (int, float)):
                yield c
            else:
                for x in c:
                    yield from points(x)
        for lon, lat, *_ in points(v):
            if not (-92 <= lon <= -75 and -5.1 <= lat <= 1.7):
                raise ValueError("La geometría debe estar dentro de Ecuador")
        return v

class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    geometry: GeoJSONPolygon
    canton_id: str | None = None
```

---

## Paso 7 · Resultados de análisis (escribe el backend)

`analysis_runs` y `rotation_strategies` **no tienen política de escritura para usuarios**:
el backend las crea con `service_client()` **después de comprobar** con `user.db` que la
finca es del usuario:

```python
def create_rotation_run(field_id: str, body: RunRequest, user: CurrentUser):
    field = fields_repo.get_field_full(user.db, field_id)       # RLS: si no es suyo → None
    if not field:
        raise HTTPException(404, "Finca no encontrada")
    result = rotation_engine.compare(field, body)                # usa climate_service (caché)
    svc = service_client()
    run = svc.table("analysis_runs").insert({
        "area_id": field_id, "kind": "rotation", "requested_by": user.id,
        "params": body.model_dump(), "temp_delta_c": body.scenario.temp_delta_c,
        "rain_delta_pct": body.scenario.rain_delta_pct,
        "monthly_calendar": result.calendar,
    }).execute().data[0]
    svc.table("rotation_strategies").insert(
        [{"run_id": run["id"], **s} for s in result.strategies]
    ).execute()
    return {**run, "strategies": result.strategies}
```

---

## Paso 8 · Probar

```bash
# Token de prueba: crear un usuario en Supabase → Authentication → Users,
# y obtener su access_token desde el frontend (supabase.auth.getSession()).
export TOKEN=...

curl -X POST http://localhost:8000/api/v1/fields \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Lote 1","geometry":{"type":"Polygon","coordinates":[[[-79.53,-1.80],[-79.52,-1.80],[-79.52,-1.79],[-79.53,-1.79],[-79.53,-1.80]]]}}'
```

Tests automáticos con `pytest` + `httpx.TestClient`, sobreescribiendo dependencias:

```python
app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u1", email="t@test", token="x")
```

## Checklist por recurso

- [ ] Modelo Pydantic (create / update parcial / respuesta)
- [ ] Repositorio con manejo de `APIError` → `raise_http`
- [ ] Router con `response_model` y códigos correctos (201, 204, 404)
- [ ] ¿Datos del usuario? → `user.db`. ¿Caché/resultados/catálogo? → `service_client()`
- [ ] Registrar router en `main.py`
- [ ] Probar en `/docs` con y sin token, y con token de otro usuario (debe dar 404)
