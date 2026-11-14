# 3. Backend (FastAPI + Supabase + Earth Engine)

Base: el backend existente de `AgriculturalUIDE/BACK` (FastAPI, GEE ya integrado). Se agregan
**ETL**, **modelo** y **API de resultados**.

## Arquitectura

```
                 ┌──────────── ETL (scripts, se corren una vez / por temporada) ───────────┐
NOAA CPC ───────►│ etl_enso         → enso_index, enso_events                              │
FAO GAUL (GEE) ─►│ etl_areas        → areas                                                │
ERA5/GPM/SMAP ──►│ etl_climate      → area_monthly_series                                  │
                 │ etl_disease      → disease_risk_monthly / disease_risk_scenario         │
                 │ etl_suitability  → crop_suitability                                     │
ESPAC/FAOSTAT ──►│ etl_production   → crop_production_stats, crop_exposure                 │
SIPA ───────────►│ etl_prices       → crop_prices                                          │
CMIP6 (GEE) ────►│ etl_scenarios    → area_scenario_climate  (Fase 2)                      │
                 └───────────────────────────────┬────────────────────────────────────────┘
                                                 ▼
                                          Supabase (Postgres)
                                                 ▲
                 ┌───────────── ML ──────────────┴──────────────┐
                 │ train.py   → model_versions, training_samples │
                 │ predict.py → loss_predictions,                │
                 │              strategy_evaluations             │
                 └───────────────────────────────────────────────┘
                                                 ▲
                 ┌──────────── API (FastAPI) ────┴──────────────┐
Frontend ◄──────►│ /api/v1/...  solo LEE resultados ya calculados │
                 └───────────────────────────────────────────────┘
```

**Regla:** la API **no calcula en vivo** con GEE (lento y con cuota). Todo se precalcula en
el ETL y la API lee Supabase → la demo responde en milisegundos.

## Estructura de carpetas

```
BACK/
├── app/
│   ├── main.py
│   ├── core/            config.py · supabase.py · gee.py
│   ├── models/          schemas Pydantic de respuesta
│   ├── repositories/    lecturas a Supabase por recurso
│   └── routers/         areas.py · scenarios.py · enso.py · risk.py · losses.py · strategies.py · meta.py
├── etl/
│   ├── etl_enso.py
│   ├── etl_areas.py
│   ├── etl_climate.py
│   ├── etl_disease.py
│   ├── etl_suitability.py
│   ├── etl_production.py
│   ├── etl_prices.py
│   ├── etl_scenarios.py          # Fase 2
│   └── run_all.py                # orquesta en orden
├── ml/
│   ├── dataset.py                # lee v_training_area_year, calcula target
│   ├── train.py
│   ├── predict.py
│   └── strategies.py
├── data/raw/                     # CSV descargados (ESPAC, FAOSTAT, SIPA) — no se versiona
└── requirements.txt
```

Dependencias nuevas: `supabase`, `pandas`, `numpy`, `scikit-learn`, `joblib`, `shap`,
`httpx` (ya está), `openpyxl` (leer XLSX de ESPAC).

## ETL: qué hace cada script

| Script | Entrada | Proceso | Salida |
|--------|---------|---------|--------|
| `etl_enso` | NOAA `oni.ascii.txt`, `sstoi.indices` | Parsear texto; ONI se fecha en el mes central del trimestre; detectar eventos (≥ 5 trimestres ONI ≥ 0.5; Niño costero: Niño 1+2 ≥ 0.4 por ≥ 3 meses) | `enso_index`, `enso_events` |
| `etl_areas` | GEE `FAO/GAUL/2015/level1`, `level2` (Ecuador) | Geometría → GeoJSON → `create` en `areas` (kind `province` / `canton`) | `areas` |
| `etl_climate` | GEE ERA5-Land diario, GPM IMERG, SMAP | Por área y año: serie diaria → contar días favorables, lluvia, saturación → agregar a mes | `area_monthly_series` |
| `etl_disease` | `area_monthly_series` diaria en memoria + `disease_thresholds` | Día favorable = cumple todas las reglas del patógeno; `risk_index = favorable_days / días_del_mes` (0–1) | `disease_risk_monthly`; promedios por escenario → `disease_risk_scenario` |
| `etl_suitability` | Climatología + `crop_requirements` + `area_static_features` | ECOCROP: puntaje 0–1 por parámetro (1 en óptimo, lineal hasta 0 en el límite absoluto); total = mínimo; factor limitante = el de menor puntaje | `crop_suitability` |
| `etl_production` | ESPAC (XLSX), FAOSTAT (ZIP) | Normalizar nombres de provincia; ha y t por año; reparto cantonal por superficie de cultivo | `crop_production_stats`, `crop_exposure` |
| `etl_prices` | SIPA (CSV) | Precio mensual del grano seco en USD/t | `crop_prices` |
| `etl_scenarios` (F2) | GEE `NASA/GDDP-CMIP6` | Delta (2041–60 − 1995–2014) por modelo y mes; sumar al observado | `area_scenario_climate` |

### Composición de escenarios históricos

- `nino`: promedio de los meses de enero–junio de los años clasificados como Niño.
- `normal`: ídem para años neutros.
- `actual`: usa la fase ENSO vigente (`enso_index` más reciente) y el escenario correspondiente.

### Detalle clave: días favorables con ERA5-Land

```python
import math

def rh_from_dewpoint(t_c, td_c):
    es = 6.112 * math.exp(17.67 * t_c  / (t_c  + 243.5))
    ea = 6.112 * math.exp(17.67 * td_c / (td_c + 243.5))
    return max(0.0, min(100.0, 100 * ea / es))

def is_favorable(day: dict, rules: list[dict]) -> bool:
    """day = {"t2m": 25.1, "rh_mean": 88, "precip": 4.2, ...}; rules = filas de disease_thresholds."""
    for r in rules:
        v = day.get(r["variable_id"])
        if v is None:
            return False
        if r["min_value"] is not None and v < r["min_value"]:
            return False
        if r["max_value"] is not None and v > r["max_value"]:
            return False
    return True
```

> Nota: la HR media diaria con la temperatura media subestima las horas de humedad nocturna.
> Es una aproximación aceptable con datos diarios; mejora usando ERA5-Land horario (Fase 3).

## API REST (`/api/v1`) — solo lectura

| Método | Ruta | Devuelve | Fase |
|--------|------|----------|------|
| `GET` | `/meta` | Fuentes, variables, modelo activo y sus métricas | 1 |
| `GET` | `/scenarios` | Lista de escenarios disponibles | 1 |
| `GET` | `/enso/current` | Fase ENSO actual, último ONI y Niño 1+2, evento en curso | 1 |
| `GET` | `/enso/history?from=1990` | Serie para gráfico | 1 |
| `GET` | `/areas?kind=canton&province=Los Rios` | Áreas (sin geometría) | 1 |
| `GET` | `/areas/geojson?kind=canton&province=...` | FeatureCollection para el mapa | 1 |
| `GET` | `/crops/cacao/requirements` | Requerimientos ECOCROP | 1 |
| `GET` | `/losses?scenario=nino&kind=canton` | Pérdida por área: `loss_pct`, intervalo, `loss_t`, `loss_usd`, `risk_class` | 1 |
| `GET` | `/losses/summary?scenario=nino` | Totales nacionales/provinciales | 1 |
| `GET` | `/areas/{id}/detail?scenario=nino` | Pérdida + factores (SHAP) + riesgo mensual por patógeno + aptitud + clima vs requerimiento | 1 |
| `GET` | `/areas/{id}/strategies?scenario=nino` | Estrategias ordenadas: pérdida esperada, pérdida evitada, por qué, evidencia, vacíos, riesgos | 1 |
| `GET` | `/compare?area_id=...&scenarios=normal,nino,ssp245_2050` | Mismo detalle en varios escenarios | 2 |
| `GET` | `/zones?future=ssp245_2050` | Matriz segura/manejo/transición/crítica | 2 |
| `POST` | `/observations` 🔒 | Registrar observación de campo | 3 |

### Ejemplo de respuesta — `/areas/{id}/detail?scenario=nino`

```json
{
  "area": {"id": "…", "name": "Vinces", "province": "Los Rios", "cacao_ha": 15200},
  "scenario": "nino",
  "loss": {
    "loss_pct": 22.4, "loss_pct_low": 12.0, "loss_pct_high": 35.1,
    "loss_t": 1830, "loss_usd": 4950000, "risk_class": "alto",
    "vs_normal": {"loss_pct": 6.1, "delta_usd": 3600000}
  },
  "top_factors": [
    {"feature": "fav_days_monilia", "label": "Días favorables a moniliasis (ene–jun)", "value": 118, "contribution_pct": 9.8},
    {"feature": "heavy_rain_days",  "label": "Días de lluvia > 50 mm",                   "value": 14,  "contribution_pct": 5.2}
  ],
  "monthly_risk": [{"month": 1, "monilia": 0.71, "phytophthora": 0.55}, "…"],
  "suitability": {"score": 0.82, "class": "apta", "limiting_factors": ["rain_annual"]},
  "model": {"name": "cacao_loss_v1", "mae": 6.3, "trained_years": [2002, 2024]},
  "disclaimer": "Estimación con datos satelitales y estadísticos. Validar con técnicos del INIAP/MAG."
}
```

*(Valores ilustrativos de formato, no resultados.)*

## Variables de entorno

```env
GEE_PROJECT=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...    # ETL y ML escriben con esta
SUPABASE_ANON_KEY=...
EARTHDATA_USER=...               # Fase 3 (AppEEARS)
EARTHDATA_PASS=...
```

## Cómo se corre

```bash
cd BACK
venv\Scripts\python -m etl.run_all --provinces "Los Rios,Guayas,Manabi,Esmeraldas,El Oro" --years 2001-2025
venv\Scripts\python -m ml.train
venv\Scripts\python -m ml.predict --scenarios normal,nino,actual
venv\Scripts\python -m uvicorn run:app --host 0.0.0.0 --port 8000
```
