# 3. Base de datos (Supabase · Postgres 17 + PostGIS)

Principio: **guardar valores agregados por área y mes, nunca imágenes satelitales**.
Las teselas del mapa se piden a GEE en vivo (sus URLs caducan, no se guardan).

## Diagrama

```
data_sources ─┐
              └─< variables >──────────────┬──────────────────┐
crops ──────────────────┐                  │                  │
                        │                  │                  │
auth.users ─┐           │                  │                  │
            └─< areas (país/provincia/cantón/finca, geom PostGIS)
                  │  ├── field_profiles          (1:1, solo fincas)
                  │  ├── field_priorities        (1:1, solo fincas)
                  │  ├──< field_current_rotation >── crops
                  │  ├── area_static_features    (1:1)
                  │  ├──< area_climatology       (área × variable × mes)
                  │  ├──< area_monthly_series    (área × variable × fecha)
                  │  └──< analysis_runs
                  │          └──< rotation_strategies
                  │                   └──< expert_reviews >── auth.users
```

## Tablas

### A. Referencia (lectura pública)

| Tabla | PK | Descripción |
|-------|----|-------------|
| `data_sources` | `id` text | Fuentes de datos (GPM, SMAP, MODIS, POWER…). **11 filas sembradas.** |
| `variables` | `id` text | Variables medidas, unidad, fuente y explicación sencilla. **15 filas sembradas.** |
| `crops` | `id` text | Catálogo de cultivos con rangos agronómicos, Kc, fijación de N, etc. **Vacío: cargar con FAO ECOCROP / FAO-56.** |

### B. Territorio

| Tabla | PK | Descripción |
|-------|----|-------------|
| `areas` | `id` uuid | País, provincia, cantón o finca. `geom` MultiPolygon 4326. `area_ha` se calcula sola. `owner_id` obligatorio si `kind='field'`. |
| `field_profiles` | `area_id` | Riego, fuente de agua, suelo observado, equipos, mercado. |
| `field_current_rotation` | `id` | Secuencia actual: `position`, `crop_id`, `start_month`, `months`. Única por (`area_id`,`position`). |
| `field_priorities` | `area_id` | Pesos 0–5: agua, ingreso, suelo, erosión, plagas, forraje + `excluded_crops`. |

### C. Caché NASA (escribe solo el backend)

| Tabla | PK | Descripción |
|-------|----|-------------|
| `area_static_features` | `area_id` | Altitud, pendiente, suelo, cobertura (`jsonb`), tendencia GRACE. |
| `area_climatology` | (`area_id`,`variable_id`,`month`) | Media mensual histórica + p10/p90. |
| `area_monthly_series` | (`area_id`,`variable_id`,`month_date`) | Serie mensual y anomalía. |

### D. Resultados

| Tabla | PK | Descripción |
|-------|----|-------------|
| `analysis_runs` | `id` uuid | Cada análisis: tipo, parámetros, escenario (`temp_delta_c`, `rain_delta_pct`), `stats`, `monthly_calendar`. |
| `rotation_strategies` | `id` uuid | Estrategias de una corrida: `sequence`, puntajes, `why`, `evidence`, `benefits`, `data_gaps`, `risks`. |
| `expert_reviews` | `id` | Validación por agricultor/agrónomo: `verdict` + comentario. |

### Formatos JSON

```jsonc
// rotation_strategies.sequence  y  body de rotación
[{ "crop_id": "maiz", "start_month": 1, "months": 4 },
 { "crop_id": "mucuna", "start_month": 5, "months": 3 }]

// rotation_strategies.evidence
[{ "variable_id": "water_balance", "source_id": "gpm_imerg",
   "statement": "Déficit hídrico de jul–oct (−80 mm/mes en promedio)" }]

// analysis_runs.monthly_calendar
[{ "month": 7, "dry": true, "heat": false, "bare_soil": true, "frost": false }]
```

## Seguridad (RLS)

Todas las tablas tienen RLS activado.

| Tabla(s) | `anon` / usuario | Backend (`service_role`) |
|----------|------------------|--------------------------|
| `data_sources`, `variables`, `crops` | Leer | Todo |
| `areas` | Leer no-fincas; CRUD **solo sus fincas** | Todo |
| `field_profiles`, `field_priorities`, `field_current_rotation` | CRUD solo si es dueño de la finca | Todo |
| `area_*`, `analysis_runs`, `rotation_strategies` | Leer si puede ver el área | Escribe |
| `expert_reviews` | Leer todo; crear/editar las propias | Todo |

Funciones auxiliares (esquema `private`, no expuestas en la API):
`private.can_read_area(uuid)` y `private.owns_area(uuid)`.

RPC expuestas (solo `authenticated`):

| Función | Uso |
|---------|-----|
| `create_field(p_name text, p_geojson jsonb, p_parent uuid)` | Crea una finca del usuario actual desde GeoJSON |
| `update_field_geom(p_id uuid, p_geojson jsonb)` | Cambia el polígono de una finca propia |

Verificado: un usuario crea su finca (`owner_id` automático, `area_ha` calculada);
otro usuario y `anon` no la ven.

## Tamaño estimado

~220 cantones × 15 variables × 12 meses ≈ 40 mil filas de climatología;
series de 20 años ≈ 800 mil filas → del orden de decenas de MB. Plan gratuito: 500 MB.
