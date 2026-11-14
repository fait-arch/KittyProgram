# Componentes · diseño atómico

Se arma de lo pequeño a lo grande. Cada nivel solo importa de los niveles inferiores.

| Nivel | Qué es | Componentes |
|---|---|---|
| `atoms/` | Una sola pieza visual, sin datos de la API | `EChart` (lienzo ECharts), `Icon`, `Button` · `LinkButton` · `IconButton`, `FilterChip`, `Badge`, `Swatch`, `Skeleton`, `HatchDefs`, `Logo` |
| `molecules/` | Dos o más átomos con un propósito | `SegmentedButton`, `ScenarioSelector`, `LegendItem`, `AlertLevelChip`, `KpiTile`, `ClassDistribution`, `LossInterval`, `SaveOfflineButton`, `StatCard` · `PanelCard`, `ChartFrame` (título + leyenda + «Ver como tabla»), `Dialog`, `CantonSearch`, `DataSourceChip` |
| `organisms/` | Secciones completas, a veces con datos (SWR) | `TopAppBar`, `EnsoBanner`, `Navigation`, `ControlPanel`, `SummaryCard`, `TopCantons`, `MapLegend`, `LossMap`, `LossTable`, `AreaSheet`, `LossHero`, `FactorBars`, `MonthlyRiskChart`, `RequirementCheck`, `StrategyCards`, `LossRangeChart`, `ClassMixChart`, `ZoneMatrix`, `ExportDialog`, `AlertScale`, `OfflineBanner`, `FincaMap`, `EarthMap` |
| `templates/` | Esqueleto de página o pieza con tamaño fijo | `AppShell`; `plantillas/ShareCard` (1080×1080), `plantillas/FichaA4` (A4), `plantillas/VideoCover` (1920×1080) |
| `screens/` | Plantilla + organismos + estado de la URL | `MapScreen`, `CompareScreen`, `MethodologyScreen`, `TemplatesScreen`, `FincaScreen`, `PanelScreen` |

## Reglas

- **Colores:** solo tokens de `src/app/globals.css` (clases `bg-primary`, `text-on-surface`…). Los hex de datos viven en
  `src/lib/design/colors.ts` porque Leaflet no acepta `var(--…)`; son los mismos de `qgis/estilos/`.
- **Verde cacao** es el color primario (botones, selección, foco, gráficos). **Deep Blue** queda para la barra superior
  y el banner de El Niño; **Neon Yellow** solo en `Badge tone="highlight"`.
- **Pérdida = alerta de 5 niveles** (IPC / SNGR). Nunca solo color: `Swatch` + texto, o `AlertLevelChip` (muestra + ícono + texto).
  El nivel Crítico lleva rayado (`.hatch-critica` en HTML, `url(#cr-hatch)` en el mapa, `LinePatternFill` en QGIS).
- **Botones:** textura con `.tex-filled` / `.tex-tonal` y capa de estado M3 `.state-layer` (hover 8 %, presionado 12 %).
- El mismo inventario está en Figma: páginas *Fundamentos*, *Átomos*, *Moléculas* y *Organismos*.

## Gráficos (fase 2)

Apache ECharts 5 (Apache-2.0) con `echarts-for-react` (MIT), importado por partes y cargado solo en el cliente.
Los colores se leen de `globals.css` en tiempo de ejecución (`src/lib/charts/tokens.ts`), así que siguen el tema
Misión/Campo sin duplicar hex. Cada gráfico va dentro de `ChartFrame`: leyenda siempre visible, tooltip con cruz
guía y «Ver como tabla». El nivel Crítico usa un *decal* rayado, igual que el mapa y QGIS.

| Gráfico | Dónde | Datos |
|---|---|---|
| `MonthlyRiskChart` · líneas con área, lluvias sombreadas, pico marcado | Panel del cantón | `/areas/{id}/detail` → `monthly_risk` |
| `FactorBars` · barras horizontales con valor | Panel del cantón | `/areas/{id}/detail` → `top_factors` |
| `LossRangeChart` · punto + rango p10–p90 sobre franjas de alerta | Comparar | `/compare` |
| `ClassMixChart` · barras apiladas al 100 % por escenario | Comparar | `/losses/summary` × 5 escenarios |

## Plantillas (fase 3)

Ruta `/plantillas?tipo=tarjeta|ficha|portada&canton=…&escenario=…` (también desde el panel del cantón:
botones «Compartir» y «Ficha A4»). Reutilizan los organismos de la app con los mismos datos de la API.

| Plantilla | Tamaño | Tema | Salida |
|---|---|---|---|
| Tarjeta para compartir | 1080 × 1080 | Misión | PNG (html-to-image) |
| Ficha para el técnico | A4 (794 × 1123 px) | Campo | Imprimir / guardar como PDF (`@page A4`) |
| Portada del video | 1920 × 1080 | Misión | PNG |

Con datos de demostración las plantillas lo dicen en el propio diseño. `[data-theme="mision"]` en
`globals.css` permite forzar el tema oscuro dentro de una pieza aunque la app esté en Campo.

## Modo Campo sin conexión (fase 4)

PWA instalable (`src/app/manifest.ts`, íconos en `public/icons/`) con un service worker propio sin dependencias
(`public/sw.js`). Solo se registra en producción (`npm run demo` o `next start`); en `npm run dev` no interfiere.

| Recurso | Estrategia |
|---|---|
| Páginas (`/`, `/comparar`, `/metodologia`, `/plantillas`) | Red primero; sin red, la última copia |
| `/_next/static`, `/mock`, `/geo`, `/qgis`, íconos, fuentes | Caché primero |
| `GET /api/v1/*` | Red primero y se guarda; sin red **o con el backend caído (503)**, la última respuesta real con `x-cr-offline: 1` |
| `/api/v1/export` | Siempre a la red |

- `SaveOfflineButton` (panel del cantón): descarga los datos del cantón en los 5 escenarios, más mapa, resúmenes,
  comparación y páginas, con avance y fecha de la copia.
- `OfflineBanner`: «Sin conexión» (con accesos a los cantones guardados) o «El servidor no responde» (datos reales guardados).
- Botón «Instalar la app» en la barra superior cuando el navegador lo ofrece.
- Para invalidar las copias guardadas tras un cambio grande, subir `VERSION` en `public/sw.js`.

## Mi finca (fase 5 · «Finca individual» de docs/06-fases.md)

Ruta `/finca?finca=lon,lat;lon,lat;…&escenario=…` (o `&ha=` con un solo punto). Se dibuja el lote con clics
(vértices arrastrables), se usa el GPS o se escriben coordenadas. Área geodésica, centroide y punto en polígono en
`src/lib/geo/finca.ts`, sin dependencias.

| Dato | Endpoint (BACK) | Demostración |
|---|---|---|
| Cantón del lote | `GET /areas/lookup?lat&lon` | punto en polígono sobre `public/mock/cantones.geojson` |
| Pérdida | `GET /areas/{id}/detail` del cantón, aplicada a las ha del lote con el rendimiento y precio implícitos del cantón | igual |
| Clima del punto | `GET /point/climate` (NASA POWER, celda ~55 km) | clima del cantón |

La pantalla dice siempre que el modelo es cantonal. Las fincas se guardan en el dispositivo («Mis fincas»).

## Mapa satelital 3D (`EarthMap`)

Botón «Mapa 2D · Satélite 3D» en el mapa principal (`?vista=satelite`). MapLibre GL JS 5 (BSD-3), sin claves:

| Capa | Fuente | Licencia / crédito |
|---|---|---|
| Satélite | Sentinel-2 sin nubes 2024 (EOX, datos Copernicus), ~10 m | CC BY-NC-SA 4.0 · uso no comercial con atribución |
| NASA hoy | NASA GIBS (Worldview): VIIRS SNPP color real del día anterior | NASA GIBS / ESDIS |
| Blue Marble | NASA GIBS: Blue Marble con relieve y batimetría | NASA GIBS |
| Relieve 3D | AWS Terrain Tiles (Terrarium) | AWS Open Data |

- **Globo / plano**, **relieve 3D**, **columnas 3D** (altura = % de pérdida) y **mazorcas de cacao** en los cantones con
  aptitud ECOCROP ≥ 0,7 (`/zones`), coloreadas por zona 2050 (verde azulado = segura, amarillo = manejo).
- Misma escala de 5 niveles que el mapa 2D y QGIS; Crítica con rayado (`fill-pattern`).
- Clic en un cantón o una mazorca abre su panel. Si un fondo no carga, se avisa y los datos siguen visibles.
- `lib/map/basemaps.ts` tiene las URL; para otra fuente (p. ej. Landsat de GIBS) basta con agregar una entrada.

## Rediseño guiado por la plantilla Harvest (TooEzra/green-tech)

- **Paleta:** el verde agrícola OKLCH de la plantilla (tono ≈ 142) llevado a nuestros roles M3. Campo = blanco verdoso
  (`#F1FAF0`), Misión = verde casi negro (`#081109`). Contrastes: texto ≥ 16:1, secundario ≥ 5,6:1.
- **Encabezado claro como tarjeta** (la plantilla usa `bg-card`); el banner de El Niño queda como franja verde oscura.
- **Barra lateral** de 224 px con ícono + nombre en pantallas grandes (riel de 80 px en medianas).
- **Panel general** (`/panel`): 4 `StatCard`, tarjetas El Niño · Cacao en la Costa · Más afectados, gráfico de niveles
  y recomendaciones. Una idea por tarjeta; nada repite el menú.
- **Menos ruido:** una sola fila de controles sobre el mapa (Mapa 2D | Satélite 3D · Pérdida | Zonas 2050 · Tabla);
  en la ficha del cantón una acción principal y «Compartir» como menú.

## Capas tipo Google Maps (`EarthMap`)

Botón **Capas** abajo a la izquierda en «Satélite 3D»:
- *Tipo de mapa:* Predeterminado (OpenFreeMap / OpenStreetMap), Satélite (Sentinel-2), NASA hoy (VIIRS), Blue Marble;
  casillas *Vista de globo* y *Etiquetas* (nombres de EOX/OSM sobre el satélite).
- *Detalles del mapa:* Relieve 3D, Columnas 3D, Cacao apto y capas NASA GIBS: Lluvia (IMERG), Vegetación (NDVI),
  Incendios (VIIRS), Temperatura de superficie, Calidad del aire (aerosoles). El nivel de zoom de cada capa se detecta
  al activarla (`resolveOverlay`); si GIBS no la sirve, el botón dice «no disponible».
- *Herramientas:* Medir distancia y área; Mi ubicación y Pantalla completa en los controles de la derecha.
