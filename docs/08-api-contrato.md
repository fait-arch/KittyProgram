# 8. Contrato de la API (FastAPI ↔ front Next.js)

> Cómo consume el front (`FRONT/`) la API del backend FastAPI. Los tipos de
> `FRONT/src/lib/api/types.ts` son el espejo de los modelos Pydantic de este documento:
> **si cambia uno, cambia el otro.** Base: [03-backend.md](03-backend.md).

## 1. Reglas

| Regla | Detalle |
|-------|---------|
| Prefijo | `/api/v1` |
| Solo lectura | La API lee resultados ya calculados por el ETL y el modelo (Supabase). Nada se calcula en vivo con GEE. |
| Formato | JSON, nombres en `snake_case`, porcentajes en 0–100, toneladas de grano seco, dólares USD. |
| Identificadores | `id` de área es un texto opaco (UUID o slug). El front no lo interpreta. |
| Escenarios | `normal` · `nino` · `actual` · `ssp245_2050` · `ssp585_2050` |
| Clases de pérdida | `baja` ≤ 5 % · `moderada` ≤ 15 % · `alta` ≤ 30 % · `muy_alta` ≤ 45 % · `critica` > 45 % (límite superior **inclusivo**, igual que QGIS; alerta de 5 niveles IPC/SNGR, ver 07 §5) |
| Errores | Formato estándar de FastAPI: `{"detail": "…"}` con 404 (área no existe), 422 (parámetro inválido), 503 (datos aún no cargados). |
| Caché | `Cache-Control: public, max-age=3600` en todo `GET` (los datos cambian por temporada, no por minuto). |

## 2. Cómo llama el front

```
Navegador ──► /api/v1/...  (Next.js, mismo origen)
                 │  proxy FRONT/src/app/api/v1/[...path]/route.ts
                 ▼
          BACKEND_URL/api/v1/...  (FastAPI, p. ej. http://localhost:8000)
```

- **Sin CORS en desarrollo:** el navegador llama al mismo origen y Next reenvía al backend.
- **Backend apagado:** el proxy responde `503 {"detail": …}` con la cabecera `x-backend-down: 1`
  (una línea en la terminal como mucho por minuto). El front deja de llamar al backend durante
  30 s y el chip «Datos de demostración» permite reintentar.
- **`NEXT_PUBLIC_DATA_MODE`:** `auto` (por defecto) usa la API y, si un endpoint falla o aún no
  existe, muestra los datos de demostración de `FRONT/public/mock` con el aviso «Datos de
  demostración»; `api` solo usa la API; `mock` no llama al backend.
- **Caché en el navegador:** SWR por clave (`["losses", "nino"]`…), sin revalidar al volver a la pestaña.

Si el front se publica en otro dominio y llama directo al backend
(`NEXT_PUBLIC_API_BASE=https://api.ejemplo.org/api/v1`), activar CORS en FastAPI:

```python
import os
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONT_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

## 3. Endpoints

| Método | Ruta | Parámetros | Respuesta | Tablas (Supabase) | Usa en el front | Fase |
|--------|------|------------|-----------|-------------------|-----------------|------|
| GET | `/meta` | — | `Meta` | `model_versions` + fuentes | Metodología | 1 |
| GET | `/scenarios` | — | `list[Scenario]` | catálogo | Selector de escenario | 1 |
| GET | `/enso/current` | — | `EnsoCurrent` | `enso_index`, `enso_events` | Banner ENSO | 1 |
| GET | `/areas` | `kind`, `province?` | `list[AreaRef]` | `areas`, `crop_exposure` | Búsqueda, selector de cantón | 1 |
| GET | `/areas/geojson` | `kind`, `province?` | GeoJSON `FeatureCollection` (props `AreaProps`) | `areas` | Mapa | 1 |
| GET | `/crops/cacao/requirements` | — | `CropRequirements` | `crop_requirements` | Clima vs requerimientos | 1 |
| GET | `/losses` | `scenario`, `kind`, `province?` | `LossesResponse` | `loss_predictions`, `crop_exposure`, `crop_prices` | Mapa, top 5, tabla | 1 |
| GET | `/losses/summary` | `scenario`, `province?` | `LossSummary` | ídem (agregado) | Tarjeta de resumen | 1 |
| GET | `/areas/{id}/detail` | `scenario` | `AreaDetail` | `loss_predictions`, `disease_risk_*`, `crop_suitability`, `area_monthly_series` / `area_scenario_climate`, `model_versions` | Panel del cantón | 1 |
| GET | `/areas/{id}/strategies` | `scenario` | `StrategiesResponse` | `strategy_evaluations` | «¿Qué hacer?» | 1 |
| GET | `/compare` | `area_id`, `scenarios` (CSV) | `CompareResponse` | ídem detalle | Comparar | 2 |
| GET | `/zones` | `future` | `ZonesResponse` | `zone_classification` | Matriz de zonas | 2 |
| GET | `/export` | `scenarios` (CSV), `format`, `crs`, `level`, `zones?` | archivo | ídem `/losses` + `/zones` | Diálogo Exportar | 1 |

**Cambios respecto a 03-backend.md** (para que el contrato sea completo):

1. `loss.vs_normal` en el detalle es `{loss_pct, delta_pct, delta_usd}`: pérdida del año normal,
   diferencia en puntos y en USD (el ejemplo anterior era ambiguo).
2. El detalle incluye `climate` (`temp_mean_c`, `rain_annual_mm`, `elevation_m`, `soil_ph`) para
   el bloque «Clima vs lo que necesita el cacao»; los rangos vienen de `/crops/cacao/requirements`.
3. `/losses/summary` incluye `n_areas` y `areas_by_class` (barra de distribución).
4. Nuevo `/export` (GeoPackage con estilo para QGIS, ver §6).
5. `/compare` recibe `scenarios=normal,nino,ssp245_2050,ssp585_2050`.

## 4. Modelos Pydantic (`app/models/schemas.py`)

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ScenarioId = Literal["normal", "nino", "actual", "ssp245_2050", "ssp585_2050"]
AreaKind = Literal["province", "canton"]
RiskClass = Literal["baja", "moderada", "alta", "muy_alta", "critica"]
Zone = Literal["segura", "manejo", "transicion", "critica"]


class Scenario(BaseModel):
    id: ScenarioId
    label: str
    group: Literal["hoy", "2050"]
    phase: Literal[1, 2]
    description: str
    available: bool
    extrapolation: bool  # True en 2050: el modelo se aplica fuera del clima de entrenamiento


class Oni(BaseModel):
    value: float
    season: str  # "ASO"
    year: int


class Nino12(BaseModel):
    anomaly_c: float
    month: str  # "2026-10"


class EnsoCurrent(BaseModel):
    phase: Literal["nino", "nina", "neutro"]
    strength: Literal["debil", "moderado", "fuerte", "muy_fuerte"] | None
    oni: Oni
    nino12: Nino12
    event_in_progress: bool
    source: str = "NOAA CPC"
    updated_at: str


class AreaRef(BaseModel):
    id: str
    name: str
    province: str
    kind: AreaKind
    cacao_ha: float | None


class LossItem(BaseModel):
    area_id: str
    loss_pct: float = Field(ge=0, le=100)
    loss_pct_low: float = Field(ge=0, le=100)   # p10
    loss_pct_high: float = Field(ge=0, le=100)  # p90
    loss_t: float | None
    loss_usd: float | None
    risk_class: RiskClass


class LossesResponse(BaseModel):
    scenario: ScenarioId
    kind: AreaKind
    model: str
    items: list[LossItem]


class Totals(BaseModel):
    loss_t: float
    loss_usd: float


class LossSummary(BaseModel):
    scenario: ScenarioId
    province: str | None
    loss_t: float
    loss_usd: float
    vs_normal: Totals | None
    n_areas: int
    areas_by_class: dict[RiskClass, int]


class Factor(BaseModel):
    feature: str          # "fav_days_monilia"
    label: str            # texto para productores
    value: float
    unit: str             # "días (ene–jun)"
    contribution_pct: float  # puntos de pérdida que aporta (SHAP)
    source: str           # "ERA5-Land", "NASA GPM IMERG"…


class MonthlyRisk(BaseModel):
    month: int = Field(ge=1, le=12)
    monilia: float = Field(ge=0, le=1)
    phytophthora: float = Field(ge=0, le=1)


class Suitability(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    score: float = Field(ge=0, le=1)
    class_: Literal["apta", "marginal", "no_apta"] = Field(alias="class")
    limiting_factors: list[str]


class AreaClimate(BaseModel):
    temp_mean_c: float
    rain_annual_mm: float
    elevation_m: float
    soil_ph: float | None


class VsNormal(BaseModel):
    loss_pct: float   # pérdida en año normal
    delta_pct: float  # puntos frente a año normal
    delta_usd: float


class AreaLoss(LossItem):
    vs_normal: VsNormal | None


class ModelInfo(BaseModel):
    name: str
    mae: float
    trained_years: tuple[int, int]


class AreaDetail(BaseModel):
    area: AreaRef
    scenario: ScenarioId
    loss: AreaLoss
    top_factors: list[Factor]
    monthly_risk: list[MonthlyRisk]
    suitability: Suitability
    climate: AreaClimate
    model: ModelInfo
    disclaimer: str = "Estimación con datos satelitales y estadísticos. Validar con técnicos del INIAP/MAG."


class RequirementParam(BaseModel):
    id: Literal["temp_mean", "rain_annual", "elevation", "soil_ph"]
    label: str
    unit: str
    optimal_min: float | None
    optimal_max: float | None
    absolute_min: float | None
    absolute_max: float | None


class CropRequirements(BaseModel):
    crop: Literal["cacao"] = "cacao"
    source: str = "ECOCROP"
    parameters: list[RequirementParam]


class Strategy(BaseModel):
    id: Literal["sanitario", "drenaje_sombra", "diversificacion"]
    rank: int
    name: str
    summary: str
    expected_loss_pct: float
    avoided_loss_t: float | None
    avoided_loss_usd: float | None
    protects_income: bool
    why: str
    evidence: str
    data_gaps: str
    risks: str


class StrategiesResponse(BaseModel):
    area_id: str
    scenario: ScenarioId
    baseline_loss_pct: float
    items: list[Strategy]


class CompareItem(BaseModel):
    scenario: ScenarioId
    loss: LossItem
    suitability: Suitability
    extrapolation: bool


class CompareResponse(BaseModel):
    area: AreaRef
    items: list[CompareItem]


class ZoneItem(BaseModel):
    area_id: str
    zone: Zone
    suitability_score: float
    risk_index: float


class ZonesResponse(BaseModel):
    future: ScenarioId
    counts: dict[Zone, int]
    items: list[ZoneItem]


class DataSource(BaseModel):
    id: str
    name: str
    provider: str
    use: str


class MetaModel(BaseModel):
    name: str
    mae: float
    skill_vs_baseline: float
    interval_coverage: float
    trained_years: tuple[int, int]


class Meta(BaseModel):
    sources: list[DataSource]
    model: MetaModel
    updated_at: str
```

`Suitability.class_` sale como `"class"` en el JSON porque FastAPI serializa con alias.

## 5. Router de ejemplo (`app/routers/losses.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.models.schemas import AreaDetail, AreaKind, LossesResponse, LossSummary, ScenarioId
from app.repositories.losses import LossRepository, get_loss_repo

router = APIRouter(prefix="/api/v1", tags=["pérdidas"])
CACHE = "public, max-age=3600"


@router.get("/losses", response_model=LossesResponse)
def list_losses(
    response: Response,
    scenario: ScenarioId = Query("nino"),
    kind: AreaKind = Query("canton"),
    province: str | None = None,
    repo: LossRepository = Depends(get_loss_repo),
):
    response.headers["Cache-Control"] = CACHE
    items = repo.losses(scenario=scenario, kind=kind, province=province)
    if not items:
        raise HTTPException(503, f"Aún no hay predicciones para el escenario '{scenario}'.")
    return LossesResponse(scenario=scenario, kind=kind, model=repo.active_model_name(), items=items)


@router.get("/losses/summary", response_model=LossSummary)
def loss_summary(response: Response, scenario: ScenarioId = "nino", province: str | None = None,
                 repo: LossRepository = Depends(get_loss_repo)):
    response.headers["Cache-Control"] = CACHE
    return repo.summary(scenario=scenario, province=province)


@router.get("/areas/{area_id}/detail", response_model=AreaDetail)
def area_detail(area_id: str, response: Response, scenario: ScenarioId = "nino",
                repo: LossRepository = Depends(get_loss_repo)):
    detail = repo.detail(area_id=area_id, scenario=scenario)
    if detail is None:
        raise HTTPException(404, "Área no encontrada")
    response.headers["Cache-Control"] = CACHE
    return detail
```

`risk_class` se calcula con la misma regla que el front y QGIS:

```python
def risk_class(pct: float) -> str:
    return "baja" if pct <= 5 else "moderada" if pct <= 15 else "alta" if pct <= 30 else "muy_alta" if pct <= 45 else "critica"
```

## 6. Exportación para QGIS (`GET /export`)

| Parámetro | Valores |
|-----------|---------|
| `scenarios` | CSV de escenarios: `normal,nino` |
| `format` | `gpkg` (recomendado) · `geojson` · `shp` · `sld` |
| `crs` | `4326` (por defecto) · `32717` (UTM 17S) |
| `level` | `canton` · `province` |
| `zones` | opcional: `ssp245_2050` agrega la capa `zonas_2050` |

| `format` | Respuesta | `Content-Type` |
|----------|-----------|----------------|
| `gpkg` | Un `.gpkg` con una capa por escenario y su estilo en `layer_styles` (usar `qgis/exportar_gpkg.py::write_styled_gpkg`) | `application/geopackage+sqlite3` |
| `geojson` / `shp` | `.zip` con los datos + un `.qml` con el mismo nombre de cada capa | `application/zip` |
| `sld` | `qgis/estilos/perdida_cacao.sld` | `application/vnd.ogc.sld+xml` |

Siempre con `Content-Disposition: attachment; filename="cacaoresiliente_<escenarios>.<ext>"`.
Campos de las capas: los de [qgis/README.md](../qgis/README.md) (≤ 10 caracteres). El campo
`fuente` lleva modelo, versión y fecha.

## 7. Verificar la integración

1. Backend en `http://localhost:8000` con `GET /api/v1/scenarios` respondiendo.
2. En `FRONT/`: `NEXT_PUBLIC_DATA_MODE=api npm run dev`. Con `api`, cualquier diferencia con este
   contrato se ve como error en pantalla en lugar de caer a los datos de demostración.
3. El chip «Datos de demostración» no debe aparecer con `auto` cuando el backend está completo.
