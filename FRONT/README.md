# CacaoResiliente · Front (Next.js)

Front de **CacaoResiliente**: *¿cuánta producción de cacao se perdería en cada cantón del Ecuador
por enfermedades asociadas a El Niño, hoy y con el clima de 2050?* — NASA Space Apps Challenge
2026, reto Field Shift.

- **Diseño:** Material Design 3 × paleta NASA Space Apps 2026 → [docs/07-propuesta-ui.md](../docs/07-propuesta-ui.md)
- **API (FastAPI):** contrato y modelos Pydantic → [docs/08-api-contrato.md](../docs/08-api-contrato.md)
- **QGIS:** estilos y exportación → [qgis/README.md](../qgis/README.md)

## Arrancar

Requiere Node.js ≥ 20.9.

```bash
cd FRONT
npm install
cp .env.example .env.local     # ajustar BACKEND_URL si el backend no está en :8000
npm run dev                    # http://localhost:3000
```

| Script | Para qué |
|--------|----------|
| `npm run dev` | Desarrollo. Usa la API y, si no responde, datos de demostración |
| `npm run dev:mock` | Solo datos de demostración (sin backend) |
| `npm run demo` | Compila y sirve en modo producción en `http://<tu-ip>:3000` (para mostrar a otros) |
| `npm run build` / `npm start` | Producción |
| `npm run typecheck` | Revisión de tipos |

## Compartir con otros en tu red

Otra persona abre `http://<tu-ip>:3000` (la IP sale en la terminal como `Network:`).

- **Para mostrar o presentar:** `npm run demo` (modo producción). Es más rápido, no expone el
  código fuente ni la recarga en caliente y no tiene restricciones de origen.
- **En desarrollo (`npm run dev`):** Next 16 bloquea con 403 la recarga en caliente cuando la
  página se abre desde un host que no es `localhost`; el resultado es una página que **se ve pero
  no responde a clics**. `next.config.ts` ya permite las IPs de tu máquina; si entran por otro
  nombre (`mi-pc.local`, un túnel), agrégalo en `ALLOWED_DEV_ORIGINS` de `.env.local` y reinicia.
- El otro navegador usa tu backend: las llamadas a `/api/v1` pasan por tu máquina hacia `BACKEND_URL`.

## Fuente de datos

| `NEXT_PUBLIC_DATA_MODE` | Comportamiento |
|-------------------------|----------------|
| `auto` (por defecto) | Llama a FastAPI. Si un endpoint falla o aún no existe, usa `public/mock` y muestra el chip **«Datos de demostración»** |
| `api` | Solo FastAPI; los errores se ven en pantalla (para verificar el contrato) |
| `mock` | Solo datos de demostración |

El navegador llama a `/api/v1/*` y el proxy `src/app/api/v1/[...path]/route.ts` lo reenvía a
`BACKEND_URL` (sin CORS). Los datos de `public/mock` son **ilustrativos**: no son resultados del modelo.

## Errores comunes

| Mensaje | Qué pasa | Qué hacer |
|---------|----------|-----------|
| `[api] Backend FastAPI no disponible en http://localhost:8000 (ECONNREFUSED)` | No hay backend escuchando en `BACKEND_URL`. La app sigue con datos de demostración y lo avisa con el chip | Levantar FastAPI (`uvicorn … --port 8000`), corregir `BACKEND_URL` en `.env.local` o usar `npm run dev:mock` |
| `[api] GET /losses respondió 404 …` | El backend responde, pero ese endpoint aún no existe o falla. Solo ese recurso usa demostración | Implementarlo según [docs/08-api-contrato.md](../docs/08-api-contrato.md) |
| Chip «Datos de demostración» en la barra | Algún dato no viene de la API | Clic en el chip: vuelve a probar el backend y recarga todo |
| Otra persona ve la página pero no puede hacer clic | `npm run dev` bloqueó su origen (WebSocket `/_next/hmr` con 403) | Usar `npm run demo`, o agregar su forma de entrar en `ALLOWED_DEV_ORIGINS` y reiniciar |

Con el backend apagado la app lo prueba una vez y lo reintenta cada 30 s; la terminal muestra
como mucho una línea por minuto.

## Pantallas

| Ruta | Pantalla | Endpoints |
|------|----------|-----------|
| `/` | Mapa de pérdidas: escenario, provincia, resumen, top 5, leyenda YlOrRd, tabla; panel del cantón (`?canton=`) | `/scenarios`, `/enso/current`, `/areas/geojson`, `/losses`, `/losses/summary`, `/areas/{id}/detail`, `/areas/{id}/strategies`, `/crops/cacao/requirements` |
| `/comparar` | Fase 2: cuatro climas lado a lado, rango p10–p90 y matriz de zonas 2050 | `/compare`, `/losses`, `/zones` |
| `/metodologia` | Fuentes, modelo, El Niño (`#enso`) | `/meta`, `/enso/current` |
| Diálogo *Exportar* | Capa para QGIS (GeoPackage con estilo, GeoJSON + QML, Shapefile, SLD), PDF y CSV | `/export` |

El estado vive en la URL (`?escenario=nino&canton=los-rios-vinces&provincia=…&capa=zonas`):
cualquier vista se comparte con un enlace.

## Estructura

```
src/
├── app/                 rutas (layout, /, /comparar, /metodologia) y globals.css (tokens M3)
├── components/
│   ├── ui/              primitivas M3: Button, SegmentedButton, FilterChip, Dialog, Icon
│   ├── shell/           TopAppBar, EnsoBanner, NavRail/NavBar, AppShell
│   ├── map/             LossMap (Leaflet), MapLegend, LossTable, MapScreen
│   ├── panel/           ControlPanel, ScenarioSelector, SummaryCard, TopCantons
│   ├── area/            AreaSheet, LossHero, FactorBars, MonthlyRiskChart, RequirementCheck, StrategyCards
│   ├── compare/         CompareScreen, LossRangeChart, ZoneMatrix
│   └── export/          ExportDialog
└── lib/
    ├── api/             types.ts (contrato), client.ts, endpoints.ts, hooks.ts (SWR), mock.ts
    ├── design/          colors.ts (YlOrRd, zonas, estados), format.ts (es-EC)
    ├── export/qgis.ts   GeoJSON + QML / SLD / CSV en el navegador
    ├── state/           useMapState (estado en la URL)
    └── theme.tsx        tema Misión (oscuro) / Campo (claro)
public/
├── mock/                datos de demostración (cantones + valores)
├── geo/                 silueta de Sierra y Amazonía (contexto del mapa)
└── qgis/                estilos .qml / .sld (copias de ../qgis/estilos)
```

## Estándares de diseño (resumen)

- **Tokens** en `src/app/globals.css` (`@theme` de Tailwind 4): roles M3 (`bg-surface-high`,
  `text-on-surface-variant`, `bg-cta`…). Tema Campo con `<html data-theme="campo">`.
- **Pérdida:** ColorBrewer **YlOrRd, 4 clases** (0–5, 5–15, 15–30, 30–100 %), límite superior
  inclusivo, borde `#232323`: idéntico a `qgis/estilos/perdida_cacao.qml`.
- **Mapa con patrón QGIS:** grilla de coordenadas, escala gráfica, norte, SRC y atribución. Sin
  teselas de fondo: funciona sin internet.
- **Nunca solo color:** cada color de dato va con número, nombre o ícono, y hay «Ver como tabla».
- **Tipografía:** Fira Sans (títulos y cifras), Overpass (texto), Fira Code (código), servidas
  localmente con `@fontsource`. Íconos: Material Symbols Rounded (Google Fonts, solo los usados).
- **Cifras** con `Intl.NumberFormat("es-EC")`: `41.000 t`, `USD 4,9 M`, `22,4 %`.
- Un solo botón relleno (acción clave) por pantalla; áreas táctiles ≥ 48 px.

## Créditos y licencias

- Geometrías de demostración: [pabl-o-ce/ecuador-geojson](https://github.com/pabl-o-ce/ecuador-geojson)
  (MIT, © 2020 Pablo Carrera Estrada), simplificadas. En producción: `/areas/geojson` (FAO GAUL).
- Fuentes Fira Sans, Overpass y Fira Code (SIL OFL) · Material Symbols (Apache 2.0) · Leaflet (BSD-2).
- No usa la insignia de la NASA ni el logo de Space Apps: solo su paleta y tipografías.
