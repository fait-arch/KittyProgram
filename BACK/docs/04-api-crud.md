# 4. API CRUD

Base: `http://<host>:8000/api/v1` · Formato: JSON · Swagger: `/docs`

## Autenticación

Las rutas marcadas 🔒 requieren el JWT de Supabase del usuario:

```
Authorization: Bearer <access_token>
```

El frontend lo obtiene con `supabase.auth.getSession()` → `session.access_token`.

## Errores comunes

| Código | Cuándo |
|--------|--------|
| `400` | Datos inválidos que pasaron Pydantic (p. ej. GeoJSON que no es polígono) |
| `401` | Falta el token o es inválido/caducado |
| `404` | No existe **o** no es del usuario (RLS lo oculta; no se distingue a propósito) |
| `409` | Conflicto de unicidad (p. ej. `position` repetida en la rotación) |
| `422` | Validación Pydantic |
| `503` | GEE no inicializado (solo endpoints que calculan) |

Forma del error: `{"detail": "mensaje"}`

---

## Cultivos — `/crops`

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/crops` | — | Lista. Filtros: `?region=costa&crop_type=legume&n_fixing=true` |
| `GET` | `/crops/{id}` | — | Detalle |
| `POST` | `/crops` | 🔒 admin | Crear |
| `PATCH` | `/crops/{id}` | 🔒 admin | Actualizar campos |
| `DELETE` | `/crops/{id}` | 🔒 admin | Borrar (falla con `409` si alguna rotación lo usa) |

"admin" = el backend comprueba que el email del usuario esté en `ADMIN_EMAILS` (variable de entorno)
y escribe con el cliente de servicio.

**POST /crops**

```json
{
  "id": "mucuna",
  "name_es": "Mucuna (frijol terciopelo)",
  "scientific_name": "Mucuna pruriens",
  "family": "Fabaceae",
  "crop_type": "cover",
  "region": ["costa", "amazonia"],
  "cycle_days": 120,
  "temp_opt_min_c": 20, "temp_opt_max_c": 30,
  "rain_min_mm_cycle": 400, "rain_max_mm_cycle": 2500,
  "n_fixing": true, "n_fix_kg_ha": 150,
  "residue_t_ha": 8, "ground_cover": 0.9,
  "drought_tolerance": 4, "waterlog_tolerance": 2,
  "source_ref": "FAO ECOCROP"
}
```

`201` → el cultivo creado.

---

## Fincas — `/fields` 🔒

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/fields` | Fincas del usuario (sin geometría para aligerar; `?with_geom=true` la incluye) |
| `POST` | `/fields` | Crear finca |
| `GET` | `/fields/{id}` | Detalle + perfil + prioridades + rotación actual |
| `PATCH` | `/fields/{id}` | Cambiar nombre y/o geometría |
| `DELETE` | `/fields/{id}` | Borrar (en cascada: perfil, rotación, caché, análisis) |

**POST /fields**

```json
{
  "name": "Lote El Guabo",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-79.53,-1.80],[-79.52,-1.80],[-79.52,-1.79],[-79.53,-1.79],[-79.53,-1.80]]]
  },
  "canton_id": "uuid-opcional-del-cantón"
}
```

`201`:

```json
{
  "id": "6f0c…",
  "kind": "field",
  "name": "Lote El Guabo",
  "parent_id": null,
  "area_ha": 123.0,
  "geometry": { "type": "MultiPolygon", "coordinates": [ … ] },
  "created_at": "2026-11-14T16:30:00Z"
}
```

Validaciones: `Polygon` o `MultiPolygon`, coordenadas dentro de Ecuador
(lon −92…−75, lat −5.1…1.7), área ≤ 5 000 ha.

---

## Perfil de la finca — `/fields/{id}/profile` 🔒

| Método | Descripción |
|--------|-------------|
| `GET` | Obtener (`404` si no se ha creado) |
| `PUT` | Crear o reemplazar (upsert) |
| `DELETE` | Borrar |

```json
{
  "irrigation": "partial",
  "water_source": "canal",
  "soil_texture_obs": "franco arcilloso",
  "soil_ph_obs": 6.2,
  "equipment": ["bomba", "manual"],
  "market_access": "intermediario en Babahoyo",
  "notes": "Se inunda la parte baja en marzo"
}
```

## Prioridades — `/fields/{id}/priorities` 🔒

`GET` / `PUT` (upsert). Todos los pesos 0–5.

```json
{
  "water_saving": 5, "income": 3, "soil_health": 4,
  "erosion_control": 2, "pest_break": 3, "forage": 0,
  "excluded_crops": ["palma_africana"]
}
```

## Rotación actual — `/fields/{id}/rotation` 🔒

| Método | Descripción |
|--------|-------------|
| `GET` | Secuencia ordenada por `position` |
| `PUT` | Reemplaza la secuencia completa (borra e inserta en orden) |
| `DELETE` | Vacía la secuencia |

```json
{
  "items": [
    { "crop_id": "arroz", "start_month": 1, "months": 4 },
    { "crop_id": "arroz", "start_month": 6, "months": 4 }
  ]
}
```

Validaciones: `crop_id` existe; meses 1–12; la suma de `months` ≤ 24.

---

## Datos NASA de un área (solo lectura)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/areas/{id}/climatology?variables=precip,et0` | 🔒* | Climatología mensual. Si no está en caché la calcula (puede tardar 10–60 s). |
| `GET` | `/areas/{id}/series?variable=ndvi&from=2015-01&to=2025-12` | 🔒* | Serie mensual + anomalía |
| `GET` | `/areas/{id}/static` | 🔒* | Altitud, pendiente, suelo, cobertura, GRACE |
| `GET` | `/sources` | — | Catálogo de fuentes |
| `GET` | `/variables` | — | Catálogo de variables |

\* Para cantones no hace falta token; para fincas sí.

Respuesta de `climatology`:

```json
{
  "area_id": "6f0c…",
  "period": [2005, 2025],
  "cached": true,
  "variables": {
    "precip": { "unit": "mm/mes", "source": "gpm_imerg",
                "months": [{"month":1,"mean":118.4,"p10":61.0,"p90":190.2}, …] }
  }
}
```

---

## Análisis de rotación — `/fields/{id}/rotation-runs` 🔒

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/fields/{id}/rotation-runs` | Ejecuta la comparación y la guarda |
| `GET` | `/fields/{id}/rotation-runs` | Historial (paginado: `?limit=20&offset=0`) |
| `GET` | `/rotation-runs/{run_id}` | Corrida + estrategias |
| `DELETE` | `/rotation-runs/{run_id}` | Borrar corrida |

**POST**

```json
{
  "n_alternatives": 3,
  "scenario": { "temp_delta_c": 1.5, "rain_delta_pct": -15 }
}
```

`201`:

```json
{
  "id": "run-uuid",
  "kind": "rotation",
  "monthly_calendar": [{"month":7,"dry":true,"heat":false,"bare_soil":true,"frost":false}, …],
  "strategies": [
    {
      "rank": 1, "name": "Arroz → Mucuna (abono verde)", "is_current": false,
      "sequence": [{"crop_id":"arroz","start_month":1,"months":4},
                   {"crop_id":"mucuna","start_month":6,"months":4}],
      "scores": {"total":78,"water":82,"nitrogen":90,"erosion":70,"organic":85,"pest_break":75,"income":55},
      "why": "Cubre el suelo en los meses secos y aporta nitrógeno para el siguiente arroz.",
      "evidence": [{"variable_id":"ndvi","source_id":"modis_ndvi",
                    "statement":"NDVI < 0.3 de jun a sep: suelo desnudo tras la cosecha"}],
      "benefits": ["+~150 kg N/ha", "Menos erosión en lluvias de enero"],
      "data_gaps": ["No hay análisis de suelo de laboratorio"],
      "risks": ["Validar con un agrónomo la disponibilidad de semilla de mucuna"]
    },
    { "rank": 4, "name": "Rotación actual", "is_current": true, … }
  ]
}
```

---

## Revisión experta — `/strategies/{id}/reviews` 🔒

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/strategies/{id}/reviews` | Listar |
| `POST` | `/strategies/{id}/reviews` | Crear (`reviewer_id` = usuario actual) |
| `PATCH` | `/reviews/{review_id}` | Editar la propia |
| `DELETE` | `/reviews/{review_id}` | Borrar la propia |

```json
{ "reviewer_role": "agronomist", "verdict": "partial",
  "comment": "Buena idea, pero la mucuna necesita control para no invadir el arroz." }
```
