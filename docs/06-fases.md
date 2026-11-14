# 6. Fases y tareas

## Estado actual (2026-11-14)

| Fase 1 | Estado |
|--------|--------|
| 1.1 Cultivo, requisitos, enfermedades, umbrales | ✅ (umbrales por validar) |
| 1.2 Territorio | ✅ 12 provincias y 126 cantones (Costa y Amazonía), con DPA |
| 1.3 El Niño | ✅ |
| 1.4 Clima mensual | 🟡 ERA5; cantones con 5–6 años (faltan 2014, 2015, 2016 parcial, 2022) |
| 1.5 Riesgo de enfermedad | 🟡 la moniliasis casi no discrimina |
| 1.6 Aptitud ECOCROP | 🟡 solo provincias |
| 1.7–1.8 Producción, precios, exposición | 🟡 ESPAC real 2023–2025; resto sintético; precio internacional |
| 1.9–1.14 Modelo real, estrategias, API, front, demo | ⏳ pendiente |
| Fase 2 y 3 | ⏳ pendiente |

Detalle y cómo completar cada punto: [09-como-conseguir-los-datos-que-faltan.md](09-como-conseguir-los-datos-que-faltan.md).

Cada fase termina en algo **demostrable**. Si el tiempo no alcanza, se presenta la última
fase completa y las siguientes como trabajo futuro.

---

## Fase 0 · Preparación (≈ 2 h)

| Tarea | Responsable | Hecho cuando |
|-------|-------------|--------------|
| Proyecto GEE registrado + `earthengine authenticate` | Backend | `/health` → `gee_ready: true` |
| Supabase: aplicar migraciones 0001 → 0005 | Backend | Tablas visibles en el dashboard |
| `.env` del backend y del front | Todos | Backend y front arrancan |
| Descargar ESPAC (cacao por provincia) y FAOSTAT (Ecuador) | Datos | CSV en `data/raw/` |

---

## Fase 1 · El Niño hoy (MVP) — responde la pregunta para el presente

**Pregunta de la fase:** *¿Cuánta producción de cacao se perdería en cada cantón por
enfermedades asociadas a El Niño, frente a un año normal?*

| # | Tarea | Capa | Tabla / endpoint |
|---|-------|------|------------------|
| 1.1 | Cargar cacao + requerimientos ECOCROP + patógenos + umbrales | BD | `crops`, `crop_requirements`, `pathogens`, `disease_thresholds` |
| 1.2 | Cargar provincias y cantones (FAO GAUL) | ETL | `areas` |
| 1.3 | Descargar ONI y Niño 1+2 y clasificar años Niño / Niña / neutro | ETL | `enso_index`, `enso_events` |
| 1.4 | Serie mensual 2001–2025 por área: ERA5-Land (T, HR), GPM (lluvia), SMAP (humedad, 2015→) | ETL | `area_monthly_series` |
| 1.5 | Índice mensual de riesgo de enfermedad por área y patógeno | ETL | `disease_risk_monthly` |
| 1.6 | Aptitud actual ECOCROP por cantón | ETL | `crop_suitability` (`scenario=normal`) |
| 1.7 | Cargar producción ESPAC/FAOSTAT y precios | ETL | `crop_production_stats`, `crop_prices` |
| 1.8 | Superficie de cacao por cantón (exposición) | ETL | `crop_exposure` |
| 1.9 | Construir dataset y **entrenar modelo** | ML | `model_versions`, `training_samples` |
| 1.10 | Predecir pérdida: escenarios `normal` y `nino` | ML | `loss_predictions` |
| 1.11 | Evaluar 4 estrategias por cantón | Backend | `strategy_evaluations` |
| 1.12 | API: escenarios, mapa de pérdidas, detalle de cantón, estrategias, estado ENSO | Backend | `/api/v1/...` |
| 1.13 | Front: mapa coroplético + selector normal/Niño + panel de cantón + estrategias + banner ENSO | Front | — |
| 1.14 | Demo de 3 cantones (p. ej. Vinces, Quevedo, Chone) | Todos | — |

**Entregable:** mapa de Ecuador con la pérdida estimada por cantón (t y USD) en año normal y
en año Niño, con intervalo de incertidumbre, factores que la explican y estrategias.

---

## Fase 2 · Clima 2050 — extiende la pregunta al futuro

**Pregunta de la fase:** *¿Cómo cambian la aptitud, el riesgo y la pérdida con el clima de
2041–2060?*

| # | Tarea | Capa | Tabla / endpoint |
|---|-------|------|------------------|
| 2.1 | NEX-GDDP-CMIP6: climatología histórica (1995–2014) y futura (2041–2060), SSP2-4.5 y SSP5-8.5, 4 modelos | ETL | `area_scenario_climate` |
| 2.2 | Método delta: clima observado + cambio proyectado | ETL | `area_scenario_climate` (`method=delta`) |
| 2.3 | Índice de enfermedad y aptitud futuros | ETL | `disease_risk_scenario`, `crop_suitability` |
| 2.4 | Aplicar el modelo de Fase 1 a los escenarios futuros | ML | `loss_predictions` |
| 2.5 | Matriz de zonas (segura / manejo / transición / crítica) | Backend | `zone_classification` |
| 2.6 | Front: escenarios 2050 + capa de matriz + comparación lado a lado | Front | — |

**Entregable:** el mismo mapa con 4 escenarios y la matriz de 4 colores.

---

## Fase 3 · Extras (si sobra tiempo)

- Finca individual: dibujar polígono y obtener su riesgo (tablas `areas` tipo `field`).
- Observaciones de campo (incidencia de moniliasis) para validar → `field_observations`.
- Ocurrencias GBIF de *M. roreri* como validación espacial.
- ECOSTRESS (AppEEARS) como capa de estrés a 70 m.
- Asistente conversacional que explica los resultados.

---

## Reparto sugerido (4 personas)

| Rol | Fase 1 | Fase 2 |
|-----|--------|--------|
| **Datos/ETL** | 1.2–1.8 | 2.1–2.3 |
| **ML** | 1.9–1.10 | 2.4 |
| **Backend** | 1.1, 1.11–1.12 | 2.5 |
| **Front + presentación** | 1.13–1.14 | 2.6 + video |
