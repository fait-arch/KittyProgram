# 2. Endpoints — contrato de la API

Base: `http://<host>:8000/api/v1` · JSON · Swagger en `/docs` · Fechas ISO (`YYYY-MM-DD`),
meses `YYYY-MM`. Cifras en unidades SI; el front formatea con `es-EC`.

**Parámetros comunes**

| Parámetro | Valores | Defecto |
|-----------|---------|---------|
| `crop` | id de `crops` | `cacao` |
| `scenario` | `normal` · `nino` · `nina` · `actual` · `ssp245_2050` · `ssp585_2050` | `nino` |
| `kind` | `province` · `canton` | `canton` |
| `province` | nombre (`Los Rios`) **o** uuid de la provincia | — (todas) |

Leyenda: **F1/F2/F3** = fase del proyecto · 🔒 = requiere `Authorization: Bearer <jwt Supabase>` ·
🛠 = admin (`ADMIN_EMAILS` o cabecera `X-Admin-Key`).

## Resumen

| # | Método | Ruta | Fase | Lee de |
|---|--------|------|------|--------|
| **Sistema** |||||
| 1 | GET | `/health` *(sin prefijo)* | F1 | Supabase ping, modelo en memoria |
| 2 | GET | `/meta` | F1 | `data_sources`, `variables`, `model_versions` |
| **Catálogos** |||||
| 3 | GET | `/crops` | F1 | `crops` |
| 4 | GET | `/crops/{crop}/requirements` | F1 | `crop_requirements` |
| 5 | GET | `/crops/{crop}/pathogens` | F1 | `pathogens` + `disease_thresholds` |
| 6 | GET | `/scenarios` | F1 | `scenarios` |
| 7 | GET | `/strategies` | F1 | `adaptation_strategies` |
| **El Niño** |||||
| 8 | GET | `/enso/current` | F1 | `enso_index`, `enso_events` |
| 9 | GET | `/enso/history` | F1 | `enso_index` |
| 10 | GET | `/enso/events` | F1 | `enso_events` |
| **Territorio** |||||
| 11 | GET | `/areas` | F1 | `areas` |
| 12 | GET | `/areas/geojson` | F1 | `areas.geom_simplified` |
| 13 | GET | `/areas/lookup` | F1 | `areas.geom_simplified` + shapely |
| 14 | GET | `/areas/{id}` | F1 | `areas`, `area_static_features`, `crop_exposure` |
| **Clima y riesgo por área** |||||
| 15 | GET | `/areas/{id}/climate` | F1 | `area_scenario_climate` |
| 16 | GET | `/areas/{id}/series` | F1 | `area_monthly_series` |
| 17 | GET | `/areas/{id}/risk` | F1 | `disease_risk_scenario` |
| 18 | GET | `/areas/{id}/risk/history` | F1 | `disease_risk_monthly` + `enso_index` |
| 19 | GET | `/areas/{id}/suitability` | F1 | `crop_suitability` |
| **Pérdidas (núcleo)** |||||
| 20 | GET | `/losses` | F1 | `v_loss_map` (modelo activo) |
| 21 | GET | `/losses/summary` | F1 | `loss_predictions` agregado |
| 22 | GET | `/areas/{id}/detail` | F1 | 7 tablas (ver [01](01-arquitectura.md)) |
| 23 | GET | `/areas/{id}/strategies` | F1 | Calculado al vuelo: pérdida + riesgo + `strategy_effects` |
| 23b | GET | `/areas/{id}/insights` | F1 | IA (Claude) sobre detalle + estrategias |
| 23c | POST | `/areas/{id}/ask` | F1 | IA (Claude): pregunta libre sobre el cantón |
| 24 | POST | `/predict` | F1.5 | Modelo en memoria + features del área |
| **Fase 2** |||||
| 25 | GET | `/compare` | F2 | igual que 22, varios escenarios |
| 26 | GET | `/zones` | F2 | `zone_classification` |
| **Punto libre** |||||
| 27 | GET | `/point/climate` | F1 | NASA POWER (proxy + caché) + lookup |
| **Validación en campo** |||||
| 28 | GET | `/observations` | F3 | `field_observations` |
| 29 | POST | `/observations` 🔒 | F3 | `field_observations` |
| 30 | GET | `/evaluations/{id}/reviews` | F3 | `strategy_reviews` |
| 31 | POST | `/evaluations/{id}/reviews` 🔒 | F3 | `strategy_reviews` |
| **Admin** |||||
| 32 | POST | `/admin/cache/clear` 🛠 | F1 | — |
| 33 | POST | `/admin/model/reload` 🛠 | F1.5 | `model_versions` + Storage |
| 34 | POST | `/admin/enso/refresh` 🛠 | F1 | NOAA CPC → `enso_index` |

**Mínimo para la demo de Fase 1:** 1, 2, 6, 8, 12, 20, 21, 22, 23. El resto suma.

---

## Sistema

### 1. `GET /health`

```json
{ "status": "ok", "supabase": true, "model_loaded": true,
  "model": "cacao_loss_v1", "mocks": false, "version": "0.1.0" }
```

`status` = `degraded` si falta Supabase o modelo; nunca devuelve 500 (sirve para el front).

### 2. `GET /meta`

Para el modal de metodología.

```json
{
  "sources":   [{"id":"gpm_imerg","name":"GPM IMERG Monthly v07","provider":"NASA","spatial_res_m":11000,"url":"…"}],
  "variables": [{"id":"rh_mean","name":"Humedad relativa media diaria","unit":"%","source_id":"era5_land","description":"…"}],
  "model": {"id":"uuid","name":"cacao_loss_v1","algorithm":"ridge","metrics":{"mae":6.3,"skill_vs_baseline":0.21},
            "train_start_year":2002,"train_end_year":2024,"n_samples":140,"created_at":"…"},
  "limitations": ["Pocas observaciones (≈140) → intervalos amplios", "…"],
  "attribution": "NASA (GPM, SMAP, …) · Contains modified Copernicus Climate Change Service information · NOAA CPC · INEC · FAO · MAG · GBIF",
  "disclaimer": "Estimación con datos satelitales y estadísticos. Validar con técnicos del INIAP/MAG."
}
```

---

## Catálogos

### 3. `GET /crops?region=costa`

`[{ "id":"cacao", "name_es":"Cacao", "scientific_name":"Theobroma cacao", "is_perennial":true, "region":["costa","amazonia"] }]`

### 4. `GET /crops/{crop}/requirements`

```json
{ "crop_id": "cacao", "source": "ECOCROP (OpenCLIM/ecocrop)",
  "numeric": [{"parameter":"temp_mean","opt_min":21,"opt_max":32,"abs_min":10,"abs_max":38,"unit":"°C","label":"Temperatura media"}],
  "categorical": [{"parameter":"drainage","value":"bien drenado (tolera periodos secos)","label":"Drenaje"}] }
```

`label` lo añade el backend (diccionario en `schemas/catalog.py`) para lenguaje de agricultor.

### 5. `GET /crops/{crop}/pathogens`

```json
[{ "id":"monilia","name_es":"Moniliasis","scientific_name":"Moniliophthora roreri",
   "organ_affected":"mazorca","spread_by":["viento","lluvia"],
   "rule_text":"Humedad ≥ 80 % y temperatura entre 20 y 28 °C",
   "thresholds":[{"variable_id":"rh_mean","min":80,"max":null,"unit":"%"},
                 {"variable_id":"t2m","min":20,"max":28,"unit":"°C"}],
   "validated": false }]
```

`validated` = todas sus reglas validadas. `rule_text` se genera en el backend.

### 6. `GET /scenarios?phase=1`

`[{ "id":"nino","name_es":"Año Niño","kind":"historical","phase":1,"period":[2001,2025],"available":true }]`

`available` = existe al menos una fila en `loss_predictions` del modelo activo con ese
escenario → el front deshabilita los que aún no tienen datos.

### 7. `GET /strategies`

Catálogo (sin evaluar): `id`, `name_es`, `description`, `targets`, rango de reducción,
`cost_usd_ha_year`, `validated`, `evidence`, `source_ref`.

---

## El Niño

### 8. `GET /enso/current`

```json
{
  "phase": "nino", "intensity": "fuerte",
  "oni":         {"value": 2.46, "month": "2026-09", "season": "ASO"},
  "nino12_anom": {"value": 5.25, "month": "2026-10"},
  "event": {"id":"nino_2026_27","start_month":"2026-05","peak_oni":2.46,"is_coastal":false},
  "active_scenario": "nino",
  "message_es": "El Niño fuerte en curso: el mar frente a Ecuador está 5.3 °C más caliente de lo normal.",
  "source": "NOAA CPC", "fetched_at": "2026-11-14T15:00:00Z"
}
```

- `intensity` (ONI): débil 0.5–0.9 · moderado 1.0–1.4 · fuerte 1.5–1.9 · muy fuerte ≥ 2.0.
  Si `enso_events` tiene el evento, se usa su `intensity`.
- `active_scenario` = qué escenario histórico representa la temporada `actual`.

### 9. `GET /enso/history?index=oni,nino12_anom&from=1990-01&to=2026-12`

`{ "oni": [{"month":"1997-11","value":2.4,"phase":"nino"}, …], "nino12_anom": […] }`

### 10. `GET /enso/events?phase=nino&from=1980`

Lista de `enso_events` (para marcar bandas en el gráfico histórico).

---

## Territorio

### 11. `GET /areas?kind=canton&province=Los Rios&has_crop=cacao`

`[{ "id":"uuid","name":"Vinces","kind":"canton","province":{"id":"uuid","name":"Los Rios"},"area_ha":70550,"crop_ha":15200 }]`

Sin geometría. `has_crop` filtra los que tienen fila en `crop_exposure` (zona cacaotera).

### 12. `GET /areas/geojson?kind=canton&province=Los Rios&tolerance=0.005`

`FeatureCollection` para Leaflet. Propiedades **mínimas** (el color se une en el front con
`/losses` por `id`, así el GeoJSON se cachea una vez para todos los escenarios):

```json
{ "type":"FeatureCollection",
  "features":[{ "type":"Feature", "id":"uuid",
                "properties":{"id":"uuid","name":"Vinces","province":"Los Rios","kind":"canton"},
                "geometry":{"type":"MultiPolygon","coordinates":[…]} }] }
```

`tolerance` (grados, `ST_SimplifyPreserveTopology`): 0.001–0.05, defecto 0.005 (~500 m).
`Content-Type: application/geo+json`.

### 13. `GET /areas/lookup?lat=-1.55&lon=-79.75`

`{ "canton": {"id":"uuid","name":"Vinces"}, "province": {"id":"uuid","name":"Los Rios"} }` —
`404` si el punto no cae en ningún cantón. Para "¿dónde está mi finca?".

### 14. `GET /areas/{id}`

```json
{ "id":"uuid","name":"Vinces","kind":"canton","province":{"id":"uuid","name":"Los Rios"},
  "area_ha":70550, "centroid":{"lat":-1.55,"lon":-79.75},
  "static":{"elevation_mean_m":18,"slope_mean_deg":1.2,"soil_ph":6.1,"soil_organic_c_gkg":14,
            "clay_pct":32,"sand_pct":28,"land_cover":{"tree":0.41,"cropland":0.37}},
  "exposure":[{"crop_id":"cacao","crop_ha":15200,"ref_year":2024,"method":"downscaled_landcover"}] }
```

---

## Clima y riesgo por área

### 15. `GET /areas/{id}/climate?scenario=nino&variables=t2m,precip,rh_mean`

Climatología mensual del escenario (`area_scenario_climate`), más el resumen anual que
necesita la comparación con ECOCROP:

```json
{ "area_id":"uuid","scenario":"nino",
  "variables":{ "precip":{"unit":"mm/mes","method":"composite","n_members":6,
                          "months":[{"month":1,"mean":310.2,"min":180.0,"max":520.4}, …],
                          "annual":3420.5} } }
```

`annual` = suma (lluvia, días) o media (temperatura, HR) según la unidad.

### 16. `GET /areas/{id}/series?variables=precip,ndvi&from=2015-01&to=2025-12&anomaly=true`

`{ "precip":[{"month":"2015-01","value":280.1,"anomaly":42.3}, …] }` — para la línea de tiempo.

### 17. `GET /areas/{id}/risk?scenario=nino`

```json
{ "area_id":"uuid","scenario":"nino",
  "pathogens":["monilia","phytophthora","escoba_bruja"],
  "months":[{"month":1,"monilia":0.71,"phytophthora":0.55,"escoba_bruja":0.62}, …],
  "peak":{"pathogen":"monilia","month":3,"risk":0.84},
  "dominant_pathogen":"monilia" }
```

`dominant_pathogen` = mayor suma ene–jun. Se usa para ordenar estrategias.

### 18. `GET /areas/{id}/risk/history?pathogen=monilia&from=2001-01&to=2025-12`

Serie `disease_risk_monthly` + ONI del mes, para mostrar "en 2016 y 2023 el riesgo se disparó".

`[{"month":"2016-02","risk_index":0.88,"favorable_days":25,"heavy_rain_days":3,"oni":2.2}]`

### 19. `GET /areas/{id}/suitability?crop=cacao&scenarios=normal,ssp245_2050`

`[{ "scenario":"normal","score":0.82,"class":"apta","limiting_factors":["rain_annual"],"details":{"temp_mean":1.0,"rain_annual":0.82} }]`

---

## Pérdidas (núcleo de la demo)

### 20. `GET /losses?scenario=nino&kind=canton&province=Los Rios&crop=cacao`

Una fila por área. Es lo que colorea el mapa.

```json
{ "scenario":"nino","crop":"cacao",
  "model":{"id":"uuid","name":"cacao_loss_v1"},
  "classes":[{"id":"bajo","max":5},{"id":"medio","max":15},{"id":"alto","max":30},{"id":"muy_alto","max":100}],
  "items":[{ "area_id":"uuid","name":"Vinces","province":"Los Rios",
             "loss_pct":22.4,"loss_pct_low":12.0,"loss_pct_high":35.1,
             "loss_t":1830,"loss_usd":4950000,"exposed_ha":15200,"risk_class":"alto" }] }
```

Solo predicciones del **modelo activo** (`model_versions.is_active = true` del `crop`).

### 21. `GET /losses/summary?scenario=nino&province=Los Rios&crop=cacao&vs=normal`

```json
{ "scenario":"nino","scope":{"kind":"province","name":"Los Rios"},
  "totals":{"exposed_ha":120000,"loss_t":41000,"loss_t_low":22000,"loss_t_high":64000,"loss_usd":110000000},
  "vs":{"scenario":"normal","loss_t":12000,"delta_t":29000,"delta_usd":78000000},
  "by_class":{"bajo":12,"medio":30,"alto":25,"muy_alto":8},
  "top_areas":[{"area_id":"uuid","name":"Vinces","loss_usd":4950000}] }
```

Los intervalos se **suman** (cota conservadora; documentado como limitación).

### 22. `GET /areas/{id}/detail?scenario=nino&crop=cacao`

Panel del cantón en **una sola llamada**:

```json
{
  "area":{"id":"uuid","name":"Vinces","province":"Los Rios","crop_ha":15200},
  "scenario":"nino",
  "loss":{"loss_pct":22.4,"loss_pct_low":12.0,"loss_pct_high":35.1,"loss_t":1830,"loss_usd":4950000,
          "risk_class":"alto","vs_normal":{"loss_pct":6.1,"delta_pct":16.3,"delta_usd":3600000}},
  "top_factors":[{"feature":"fav_days_monilia","label":"Días muy húmedos que favorecen la moniliasis (ene–jun)",
                  "value":118,"contribution_pct":9.8}],
  "monthly_risk":[{"month":1,"monilia":0.71,"phytophthora":0.55}],
  "dominant_pathogen":"monilia",
  "requirement_check":[
     {"parameter":"temp_mean","label":"Temperatura","value":26.1,"unit":"°C","opt":[21,32],"abs":[10,38],"status":"ok"},
     {"parameter":"rain_annual","label":"Lluvia anual","value":3420,"unit":"mm","opt":[1200,3000],"abs":[900,7600],"status":"warn"},
     {"parameter":"altitude","label":"Altitud","value":18,"unit":"m","opt":[null,900],"status":"ok"}],
  "suitability":{"score":0.82,"class":"apta","limiting_factors":["rain_annual"]},
  "model":{"name":"cacao_loss_v1","mae":6.3,"trained_years":[2002,2024],"validated_thresholds":false},
  "data_gaps":["Umbrales de enfermedad no validados en campo","Producción cantonal estimada desde la provincial"],
  "disclaimer":"Estimación con datos satelitales y estadísticos. Validar con técnicos del INIAP/MAG."
}
```

`requirement_check.status`: `ok` dentro del óptimo · `warn` entre óptimo y absoluto · `bad`
fuera del absoluto. Lo calcula el backend con `area_scenario_climate` + `crop_requirements` +
`area_static_features`. `label` de `top_factors` sale del diccionario de features (ver [03](03-integracion-ml.md)).

### 23. `GET /areas/{id}/strategies?scenario=nino&crop=cacao&priorities=ingreso:5,costo:4,suelo:2`

Estrategias evaluadas para ese cantón (≥ 3 + la actual, como pide el reto).

```json
{ "area_id":"uuid","scenario":"nino","baseline_loss_pct":22.4,
  "priorities_applied":{"ingreso":5,"costo":4,"suelo":2},
  "items":[{
     "rank":1,"strategy_id":"sanitario","name_es":"Manejo sanitario","evaluation_id":"uuid",
     "expected_loss_pct":13.4,"avoided_loss_usd":1800000,"net_benefit_usd":1250000,
     "cost_usd_ha_year":36,
     "why":"La moniliasis domina el riesgo de este cantón en ene–mar.",
     "evidence":[{"variable_id":"rh_mean","source_id":"era5_land","statement":"118 días con HR ≥ 80 % en ene–jun en años Niño"}],
     "benefits":["Reduce inóculo de moniliasis y mazorca negra"],
     "data_gaps":["Reducción de pérdida tomada de literatura, no medida en Vinces"],
     "risks":["Requiere mano de obra semanal en época lluviosa"],
     "validated":false, "reviews":{"count":0,"agree":0}
  }, {"rank":4,"strategy_id":"actual","name_es":"Manejo actual","is_current":true, "…":"…"}] }
```

- Sin `priorities` → orden de `strategy_evaluations.rank` (beneficio neto).
- Con `priorities` (`ingreso`, `costo`, `suelo`, `agua`, `mano_obra`; 0–5) → el backend
  **reordena en vivo** con un puntaje ponderado (fórmula en [05](05-pendientes.md) § D3).
  Responde a "farmer priorities" del reto sin recalcular nada.

### 24. `POST /predict` (what-if) — F1.5

Sliders del reto ("scenario sliders that adjust rainfall or temperature").

```json
// request
{ "area_id":"uuid", "crop":"cacao", "base_scenario":"normal",
  "adjust":{"temp_delta_c":1.0, "rain_delta_pct":25, "nino12_anom":3.0, "oni":2.0} }
```

```json
// response
{ "area_id":"uuid","base_scenario":"normal",
  "features_used":{"fav_days_monilia":131,"heavy_rain_days":17,"nino12_anom_jan_jun":3.0,"…":0},
  "loss_pct":27.9,"loss_pct_low":15.2,"loss_pct_high":41.0,"loss_t":2280,"loss_usd":6150000,
  "risk_class":"alto","delta_vs_base_pct":21.8,
  "top_factors":[…],
  "model":{"name":"cacao_loss_v1"},
  "warning":"Combinación fuera del rango de entrenamiento: interpretar con cautela." }
```

Cómo se recalculan las features con los ajustes: ver [03-integracion-ml.md](03-integracion-ml.md) § 4.
`503` si el modelo no está cargado. Límite: `temp_delta_c` −3…+4, `rain_delta_pct` −50…+100.

---

## Fase 2

### 25. `GET /compare?area_id=uuid&scenarios=normal,nino,ssp245_2050&crop=cacao`

`{ "area_id":"uuid", "items":[ <detail reducido por escenario: loss, suitability, dominant_pathogen> ] }`

### 26. `GET /zones?future=ssp245_2050&crop=cacao&province=…`

`[{ "area_id":"uuid","name":"Chone","zone_class":"transicion","suitability_now":0.8,"suitability_future":0.55,"nino_risk":0.7 }]`

Leyenda: **segura** (apta y riesgo bajo) · **manejo** (apta, riesgo alto) · **transición**
(pierde aptitud) · **crítica** (pierde aptitud y riesgo alto).

---

## Punto libre

### 27. `GET /point/climate?lat=-1.80&lon=-79.53&start=2005&end=2024`

Para cuando el usuario hace clic fuera de la zona precalculada o quiere "su finca".

```json
{ "point":{"lat":-1.80,"lon":-79.53}, "canton":{"id":"uuid","name":"Babahoyo"},
  "source":"NASA POWER (AG)", "resolution_km":55,
  "monthly_climatology":{"T2M":{"1":26.1,"…":0},"RH2M":{…},"PRECTOTCORR":{…}},
  "requirement_check":[…],
  "warning":"Celda de ~55 km: en la Costa puede subestimar la temperatura (ver docs/APIS-DATOS.md §13)." }
```

Si el punto cae en un cantón con datos, el front debería mostrar además el `detail` de ese
cantón (que es la fuente principal).

---

## Validación en campo — F3

### 28–29. `/observations`

`GET ?area_id=&pathogen=&source=gbif` → lista (pública).
`POST` 🔒 `{ "pathogen_id":"monilia","observed_on":"2026-11-10","lat":-1.55,"lon":-79.75,"pods_total":50,"pods_diseased":12,"severity":3,"notes":"…" }`
→ `area_id` lo resuelve el backend con `area_at_point`; `source` = `agricultor` o `tecnico`
según el rol; `observer_id` = usuario. Se escribe con el **cliente de usuario** (RLS).

### 30–31. `/evaluations/{id}/reviews`

`POST` 🔒 `{ "reviewer_role":"agronomo","verdict":"parcial","comment":"…" }`.

---

## Admin

| Ruta | Hace |
|------|------|
| `POST /admin/cache/clear` | Vacía la caché en memoria. Lo llama ML al terminar `predict.py`. |
| `POST /admin/model/reload` | Vuelve a leer `model_versions` activo y descarga el artefacto. |
| `POST /admin/enso/refresh` | Descarga ONI y Niño 1+2 de NOAA y hace *upsert* en `enso_index` (rápido, sin GEE). |

Protegidos por `X-Admin-Key: <ADMIN_API_KEY>` (scripts) o JWT de un email en `ADMIN_EMAILS`.
