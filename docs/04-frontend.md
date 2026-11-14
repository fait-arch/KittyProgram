# 4. Frontend (Next.js + Leaflet)

Base: el front existente de `AgriculturalUIDE/front` (Next.js 16, React 19, Tailwind 4,
Leaflet). Se reorganiza alrededor de **una sola pregunta**: *¿cuánto cacao se pierde aquí con
El Niño?*

## Pantalla principal

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ⚠ El Niño FUERTE en curso — ONI +2.46 · Niño 1+2 +5.25 °C   [¿Qué significa?] │  ← EnsoBanner
├───────────────┬────────────────────────────────────────────────────────────┤
│ Escenario     │                                                            │
│ ○ Año normal  │                MAPA (cantones coloreados                   │
│ ● Año Niño    │                 por pérdida estimada %)                    │
│ ○ Temporada   │                                                            │
│   actual      │                                                            │
│ ── Fase 2 ──  │                                       ┌──────────────┐     │
│ ○ 2050 mod.   │                                       │ Leyenda      │     │
│ ○ 2050 alto   │                                       │ ■ < 5 %      │     │
│               │                                       │ ■ 5–15 %     │     │
│ Provincia ▾   │                                       │ ■ 15–30 %    │     │
│               │                                       │ ■ > 30 %     │     │
│ Total Costa:  │                                       └──────────────┘     │
│ 41 000 t      │                                                            │
│ USD 110 M     │                                                            │
└───────────────┴────────────────────────────────────────────────────────────┘
        clic en un cantón ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ VINCES · Los Ríos · 15 200 ha de cacao                         [Comparar]  │
│ Pérdida estimada (año Niño): 22 %  (12 – 35 %) · 1 830 t · USD 4.9 M       │
│ vs año normal: +16 puntos                                                  │
│ ── ¿Por qué? ──────────────────────────────────────────────────────────── │
│ ▇▇▇▇▇▇▇▇▇ Días favorables a moniliasis   ▇▇▇▇ Lluvia > 50 mm  ▇▇ Suelo sat.│
│ ── Riesgo mes a mes ──────────────────────────────────────────────────── │
│  E  F  M  A  M  J  J  A  S  O  N  D   (barras moniliasis / mazorca negra)  │
│ ── Clima vs lo que necesita el cacao ─────────────────────────────────── │
│  Temp 26 °C ✓ (21–32)   Lluvia 3 400 mm ⚠ (>3 000)   Altitud 15 m ✓        │
│ ── Qué hacer ─────────────────────────────────────────────────────────── │
│ 1. Manejo sanitario      evita ≈ USD 1.8 M   [Por qué · Evidencia · Riesgos]│
│ 2. Drenaje + sombra      evita ≈ USD 0.9 M                                  │
│ 3. Diversificación       protege el ingreso                                 │
│ ⓘ Estimación con datos NASA. Validar con técnicos del INIAP/MAG.            │
└────────────────────────────────────────────────────────────────────────────┘
```

*(Cifras ilustrativas de diseño.)*

## Componentes

| Componente | Qué muestra | Endpoint |
|------------|-------------|----------|
| `EnsoBanner` | Fase ENSO actual con ONI y Niño 1+2; enlace a explicación | `GET /enso/current` |
| `ScenarioSelector` | normal · Niño · actual · (F2) 2050 moderado/alto | `GET /scenarios` |
| `LossMap` | Coroplético Leaflet por cantón (`L.geoJSON` + `style` por `loss_pct`) | `GET /areas/geojson` + `GET /losses` |
| `SummaryCard` | Total de pérdida (t, USD) del escenario y provincia | `GET /losses/summary` |
| `AreaPanel` | Pérdida, intervalo, comparación con normal | `GET /areas/{id}/detail` |
| `FactorBars` | Contribución de cada factor (SHAP) en lenguaje simple | idem |
| `MonthlyRiskChart` | Barras de riesgo por mes y patógeno | idem |
| `RequirementCheck` | Clima de la zona vs requerimientos ECOCROP (✓ / ⚠ / ✗) | idem + `/crops/cacao/requirements` |
| `StrategyCards` | Estrategias ordenadas; cada una despliega *por qué*, *evidencia*, *datos que faltan*, *riesgos* | `GET /areas/{id}/strategies` |
| `CompareView` (F2) | Mismo cantón en normal / Niño / 2050 lado a lado | `GET /compare` |
| `ZoneMatrixLayer` (F2) | Capa de 4 colores: segura, manejo, transición, crítica | `GET /zones` |
| `MethodologyModal` | Fuentes, modelo, métricas, limitaciones | `GET /meta` |
| `Disclaimer` | "Apoya, no reemplaza al técnico" — siempre visible | — |

## Reutilización del código actual

| Existe | Se reutiliza para |
|--------|-------------------|
| `LeafletMap` en `page.tsx` (carga Leaflet, capas, `fitBounds`) | `LossMap`: cambiar tiles de GEE por `L.geoJSON` coloreado |
| `LocationPanel` (provincia/cantón) | Filtro de provincia |
| `ResultsPanel` + `SUIT_ROWS` | `AreaPanel` / `SummaryCard` |
| `ChatPanel` | Fase 3: preguntas sobre el resultado |
| `getBackendUrl()` | Igual |

## Estado y datos

- Estado global mínimo con `useState`/`useReducer`: `scenario`, `province`, `selectedAreaId`.
- Cache en memoria por `scenario` (los resultados no cambian durante la sesión).
- Paleta de pérdida secuencial (claro → oscuro), con leyenda y valores; nunca solo color.
- Cifras formateadas en español (`Intl.NumberFormat('es-EC')`).

## Accesibilidad y lenguaje

- Textos para agricultores: "días con mucha humedad" en lugar de "HR ≥ 80 %"; el detalle técnico
  va en "Ver más".
- Funciona en móvil (el panel del cantón se vuelve hoja inferior).
- Atribución de datos en el pie: NASA, Copernicus (ERA5), NOAA, INEC, FAO, MAG.
