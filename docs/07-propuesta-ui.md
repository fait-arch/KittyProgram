# 7. Propuesta UI/UX — Material 3 × NASA Space Apps

> Complementa [04-frontend.md](04-frontend.md) (pantallas, componentes y endpoints). Aquí se
> define **cómo se ve y se usa**: sistema de diseño, pantallas, guion de la demo e
> implementación. Lienzo con las 7 pantallas (privado hasta compartirlo):
> <https://claude.ai/artifact/4h4wX7wh1Z6DvDD7uPxuFX>

**Base:** estructura, componentes y accesibilidad de **Material Design 3** (Google) +
color y tipografía de la **guía de marca NASA Space Apps 2026** + **verde cacao** como color
primario (fase 1 del rediseño, §15). Los componentes siguen **diseño atómico** (átomos →
moléculas → organismos → plantillas → pantallas) en el código y en Figma. No se usa la insignia de la
NASA ni el logo de Space Apps: solo su paleta y sus tipografías.

## 1. Principios

| Principio | Qué significa en la pantalla |
|-----------|------------------------------|
| **Una pregunta, un mapa** | Todo responde *¿cuánto cacao se pierde aquí?* El mapa es la pantalla; lo demás son paneles y hojas sobre él. |
| **Nunca solo color** | Cada color de dato va con número, nombre o ícono; hay vista de tabla; paletas validadas para daltonismo. |
| **Lenguaje de finca** | "Días con mucha humedad" antes que "HR ≥ 90 %". El detalle técnico vive en "Ver más". |
| **Honestidad** | Rango p10–p90 siempre junto a la cifra; aviso "validar con INIAP/MAG" siempre visible; 2050 marcado como extrapolación. |

## 2. Dos temas

| Tema | Cuándo | Por qué |
|------|--------|---------|
| **Misión** (oscuro) | Escritorio, proyector, demo y video | Identidad Space Apps; los datos "brillan" sobre el azul profundo. |
| **Campo** (claro) | Móvil del productor o técnico, al aire libre | Se lee a pleno sol. La barra superior sigue en Deep Blue (ancla de marca). |

Se cambia con `data-theme="mision" | "campo"` en `<html>`; por defecto: Misión en escritorio,
Campo en móvil (`prefers-color-scheme` como respaldo).

## 3. Paleta de marca (Space Apps 2026)

| Color | Hex | Uso en la app |
|-------|-----|---------------|
| Deep Blue | `#07173F` | Fondo Misión; tinta (texto) del tema Campo |
| Electric Blue | `#0042A6` | Inicio del degradado oficial (banner ENSO); botón de exportar en la barra |
| Neon Blue | `#0960E1` | Serie «moniliasis» en Campo |
| Blue Yonder | `#2E96F5` | Serie «moniliasis» en Misión; ícono de ENSO neutral |
| Neon Yellow | `#EAFE07` | Solo etiquetas cortas (`Badge`: FASE 2, RECOMENDADO, F2) y el enlace del banner ENSO. Nunca fondo ni titular. |
| Rocket Red | `#E43700` | Reservado para alertas de la marca. Nunca fondo; siempre con texto o ícono. |
| Martian Red | `#8E1100` | `error-container` (Misión) |
| White | `#FFFFFF` | Superficie de Campo; texto sobre azules |

Reglas de la guía que respetamos: texto largo solo sobre Deep Blue, Electric Blue o blanco;
contraste ≥ 4,5:1; degradado Electric Blue → Deep Blue a 45° (solo en el banner ENSO y
portadas); regla 60-30-10.

## 4. Roles de color Material 3

| Rol M3 | Misión (oscuro) | Campo (claro) |
|--------|-----------------|---------------|
Primario **verde cacao** (rampa tonal OKLCH, tono ≈ 150°). Deep Blue sigue como ancla de
marca: barra superior y banner ENSO en ambos temas.

| Rol M3 | Misión (oscuro) | Campo (claro) |
|--------|-----------------|---------------|
| `primary` / `on-primary` | `#5BDB87` / `#032110` | `#0A6D37` / `#FFFFFF` |
| `primary-container` / `on-…` | `#085630` / `#D1F2D7` | `#D1F2D7` / `#012A14` |
| `secondary-container` (selección) | `#0F3F2E` / `#D1F2D7` | `#D3ECDB` / `#012A14` |
| `cta` (botón relleno) / `on-cta` | `#6CE98D` / `#032110` | `#006731` / `#FFFFFF` |
| `link` | `#6CE98D` | `#0A6D37` |
| `surface` | `#07173F` | `#F8FBF8` |
| `surface-container-lowest` | `#040C24` | `#FFFFFF` |
| `surface-container-low` | `#0A1C48` | `#F2F7F2` |
| `surface-container` | `#0E2252` | `#ECF2EC` |
| `surface-container-high` | `#13295D` | `#E6EEE6` |
| `surface-container-highest` | `#1A3268` | `#DEE8DE` |
| `on-surface` / `on-surface-variant` | `#EAF0FF` / `#B3C1E0` | `#07173F` / `#3F5247` |
| `outline` / `outline-variant` | `#6F82AE` / `#2A3F72` | `#748677` / `#C2CEC4` |
| `error` / `error-container` | `#FF8A6B` / `#8E1100` | `#B32C00` / `#FFDAD2` |

Contraste medido (WCAG 2): `on-primary` sobre `primary` 9,7:1 (Misión); blanco sobre `cta`
7,0:1 (Campo); texto principal 15,3:1 (Misión) y 16,7:1 (Campo); `on-surface-variant` sobre
`surface-high` 7,1:1 (Campo); verde `#5BDB87` sobre Deep Blue 9,9:1.

## 5. Colores de datos

**Pérdida estimada: alerta de 5 niveles (colores con significado):**

| Nivel | Rango `loss_pct` | Color (app y QGIS) | Referencia | Ícono |
|-------|------------------|--------------------|------------|-------|
| Baja | 0 – 5 % | `#B2FFD8` verde menta | IPC fase 1 · sin alerta | `check_circle` |
| Moderada | 5 – 15 % | `#FAE61E` amarillo | IPC 2 · **alerta amarilla** SNGR | `info` |
| Alta | 15 – 30 % | `#E67800` naranja | IPC 3 · **alerta naranja** SNGR | `warning` |
| Muy alta | 30 – 45 % | `#C80000` rojo | IPC 4 · **alerta roja** SNGR | `error` |
| Crítica | 45 – 100 % | `#640000` + **rayado blanco a 45°** | IPC 5 | `dangerous` |

Por qué estos colores: son los de la **Clasificación Integrada de Fases (IPC)** que usan la FAO
y FEWS NET para crisis alimentarias, y coinciden con el **semáforo de alertas de la Secretaría
de Gestión de Riesgos** de Ecuador (amarilla = amenaza activada, naranja = inminente, roja =
evento en curso), el mismo que activó la alerta roja nacional por El Niño (agosto 2026). Un
técnico del MAG o un productor ya los lee sin leyenda. El verde menta de "Baja" (no el verde
IPC `#CDFACD`) separa mejor la fase 1 de la 2 (ΔE 16,3; con daltonismo 15,9). El nivel
Crítico lleva rayado, como "hambruna probable" en FEWS NET, porque el rojo oscuro casi no
contrasta con el fondo azul (1,4:1): así se distingue en pantalla, impreso, en escala de grises
y en QGIS (`LinePatternFill`, 45°, blanco 70 %).

Reglas de QGIS que seguimos: límite superior inclusivo (5,0 % = Baja), leyenda ascendente con
rótulos `0 – 5`, borde `#232323` de 0,26 mm, y en el mapa: grilla de coordenadas, escala gráfica,
flecha norte y SRC. **Selección del cantón:** halo ancho (Misión `#040C24`, Campo blanco) + trazo
fino (Misión blanco, Campo Deep Blue) en una capa aparte: se ve igual sobre el verde menta y
sobre el rojo oscuro. Fuera del alcance (Sierra/Amazonía): superficie neutra.

**Matriz de zonas 2050 (semáforo, siempre con nombre + ícono; igual en ambos temas):**

| Zona | Cuadrante | Ícono | Color |
|------|-----------|-------|-------|
| Segura | aptitud alta · riesgo bajo | `verified` | `#007C83` verde azulado |
| Manejo | aptitud alta · riesgo alto | `handyman` | `#EBC831` amarillo |
| Transición | aptitud baja · riesgo bajo | `swap_horiz` | `#DE6F00` naranja |
| Crítica | aptitud baja · riesgo alto | `report` | `#B7191C` rojo |

"Segura" es verde azulado y no verde puro: con protanopía un verde se confunde con el amarillo
de "Manejo" (ΔE 4); el verde azulado pasa (ΔE 14,1). Texto sobre cada color: blanco en Segura y
Crítica, Deep Blue en Manejo y Transición (≥ 4,9:1).

**Series y estados:** moniliasis `#2E96F5` (Campo `#0960E1`), mazorca negra `#d95926`
(Campo `#eb6834`). Estados de requerimientos ECOCROP (reservados, nunca como serie):
dentro del óptimo `#0ca30c` ✓, fuera del óptimo `#fab219` ⚠, marginal `#ec835a`,
fuera del límite `#d03b3b`, siempre con ícono y texto.

## 6. Tipografía (escala M3 con fuentes de la marca)

| Rol M3 | Fuente · tamaño/alto | Uso |
|--------|----------------------|-----|
| Display L | Fira Sans Black 57/64 | Cifra de pérdida del cantón ("22,4 %") |
| Headline L / S | Fira Sans ExtraBold 32/40 · 26/32 | Títulos de pantalla |
| Title L | Fira Sans Bold 20/28 | Secciones del panel ("¿Por qué?", "¿Qué hacer?") |
| Title M | Overpass SemiBold 16/24 | Títulos de tarjeta |
| Body L / M | Overpass Regular 16/24 · 14/20 | Texto |
| Label L / S | Overpass SemiBold 14/20 · 11/16 mayúsculas | Botones, chips, rótulos |
| Código | Fira Code | Valores técnicos en "Ver más" |

Cifras con `font-variant-numeric: tabular-nums`. Íconos: **Material Symbols Rounded**.

## 7. Forma, espaciado y elevación

- Esquinas M3: XS 4 (leyenda) · S 8 (chips) · M 12 (tooltips, controles del mapa) · L 16
  (tarjetas) · XL 28 (hojas inferiores) · Full (botones, búsqueda, segmentado).
- Rejilla de 4 px (4, 8, 12, 16, 24, 32, 48). Áreas táctiles ≥ 48 px.
- Elevación por tono de superficie (`container-low` → `highest`); sombra solo en hojas,
  menús y la tarjeta flotante del mapa.

## 8. Pantallas (lienzo de diseño)

| # | Pantalla | Patrones M3 | Endpoints |
|---|----------|-------------|-----------|
| 01 | **Mapa de pérdidas** (escritorio, interactivo): banner ENSO, riel de navegación, panel con escenario, resumen, top 5 cantones; mapa con tarjeta del cantón, leyenda, capas y "Ver como tabla" | Top app bar + search bar, banner, navigation rail, segmented button, filter chips, filled card, list, rich tooltip | `/enso/current`, `/scenarios`, `/areas/geojson`, `/losses`, `/losses/summary` |
| 02 | **Panel del cantón** (Vinces): pérdida + rango, t y USD, factores, riesgo mes a mes, clima vs requerimientos, estrategias | Side sheet, cards, tabs, lists con íconos de estado | `/areas/{id}/detail`, `/crops/cacao/requirements`, `/areas/{id}/strategies` |
| 03 | **Móvil · mapa**: escenario, mapa de la Costa central, hoja inferior con el cantón | Top app bar, segmented button, bottom sheet, navigation bar | ídem 01 |
| 04 | **Móvil · detalle**: lenguaje de finca, "¿Qué hacer?", "Enviar a mi técnico" | Full-screen dialog, cards, chips como pestañas | ídem 02 |
| 05 | **Fase 2 · comparar + matriz**: 4 climas lado a lado, gráfico de rango, matriz 2×2 y mapa de zonas | Cards en rejilla, segmented button, outlined cards | `/compare`, `/zones` |
| 06 | **Sistema de diseño**: paleta, roles, datos, tipografía, forma, componentes | — | — |
| 07 | **Exportar** (interactivo): capa para QGIS (GeoPackage con estilo, GeoJSON/Shapefile + QML, SLD), SRC, nivel, campos y vista previa de la leyenda; pestañas para PDF/PNG y CSV | Dialog, tabs, filter chips, radio list, select | `/export` (nuevo) |

**Cambio respecto a 04-frontend.md:** en escritorio el detalle del cantón pasa de "panel debajo
del mapa" a **hoja lateral (side sheet)** para que el mapa siga visible; en móvil se mantiene la
hoja inferior.

Las cifras de las pantallas son **ilustrativas de diseño**. Límites cantonales del mockup:
[pabl-o-ce/ecuador-geojson](https://github.com/pabl-o-ce/ecuador-geojson) (MIT); en la app
vienen de `/areas/geojson` (FAO GAUL).

## 9. Qué dato de la NASA se ve dónde

| Fuente | Se ve como |
|--------|-----------|
| GPM IMERG | "Días de lluvia muy fuerte (> 50 mm)"; serie de mazorca negra |
| SMAP | "Días con el suelo encharcado" |
| SRTM | Altitud en "Clima vs lo que necesita el cacao"; zonas bajas |
| MODIS NDVI | Vigor del cacaotal (NDVI y su anomalía) en "Ver más" del panel del cantón |
| NEX-GDDP-CMIP6 | Escenarios 2050 (SSP2-4.5 y SSP5-8.5) y matriz de zonas |
| ERA5-Land (Copernicus) | "Días húmedos y templados" (moniliasis) |
| NOAA CPC | Banner ENSO (ONI y Niño 1+2) |

## 10. Guion de la demo (≈ 3 min)

| Tiempo | Pantalla | Qué se dice / hace |
|--------|----------|--------------------|
| 0:00 | 01 | La pregunta + banner: El Niño fuerte en curso (ONI +2,46; Niño 1+2 +5,25 °C). |
| 0:20 | 01 | Escenario "Normal" → "Año Niño": el mapa se enciende; total de la Costa en t y USD. |
| 0:50 | 01 → 02 | Clic en **Vinces**: 22 % (12–35 %), 1.830 t, USD 4,9 M, +16 pts vs normal. |
| 1:20 | 02 | "¿Por qué?": humedad (ERA5), lluvia fuerte (GPM), suelo encharcado (SMAP). |
| 1:50 | 02 | "¿Qué hacer?": manejo sanitario evita ≈ USD 1,8 M; evidencia y riesgos. |
| 2:15 | 03 → 04 | Lo mismo en el celular del productor, con palabras de finca. |
| 2:35 | 05 | Fase 2: Vinces en 2050 y la matriz de zonas. |
| 2:55 | — | Cierre: incertidumbre explícita; apoya, no reemplaza al técnico. |

Cantones de respaldo: **Quevedo** y **Chone** (tarea 1.14).

## 11. Implementación (Next.js 16 + Tailwind 4 + Leaflet)

**Tokens en `app/globals.css`** (Tailwind 4 genera `bg-primary`, `text-on-surface`, etc.):

```css
@import "tailwindcss";

/* Fuentes de next/font: "inline" porque referencian otras variables */
@theme inline {
  --font-display: var(--font-fira-sans), ui-sans-serif, system-ui, sans-serif;
  --font-sans: var(--font-overpass), ui-sans-serif, system-ui, sans-serif;
  --font-mono: var(--font-fira-code), ui-monospace, monospace;
}

@theme {
  --radius-xs: 4px; --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-xl: 28px;

  /* Misión (por defecto) */
  --color-primary: #2E96F5;          --color-on-primary: #04122F;
  --color-primary-container: #0042A6; --color-on-primary-container: #DCE8FF;
  --color-secondary-container: #1E3A78;
  --color-accent: #EAFE07;           --color-on-accent: #07173F;
  --color-surface: #07173F;          --color-surface-lowest: #040C24;
  --color-surface-low: #0A1C48;      --color-surface-container: #0E2252;
  --color-surface-high: #13295D;     --color-surface-highest: #1A3268;
  --color-on-surface: #EAF0FF;       --color-on-surface-variant: #B3C1E0;
  --color-outline: #6F82AE;          --color-outline-variant: #2A3F72;
  --color-error: #FF8A6B;
}

[data-theme="campo"] {
  --color-primary: #0042A6;          --color-on-primary: #FFFFFF;
  --color-primary-container: #D9E5FF; --color-on-primary-container: #07173F;
  --color-secondary-container: #DDE6F7;
  --color-accent: #0960E1;           --color-on-accent: #FFFFFF;
  --color-surface: #F8FAFF;          --color-surface-lowest: #FFFFFF;
  --color-surface-low: #F2F5FC;      --color-surface-container: #ECF0F9;
  --color-surface-high: #E6EBF5;     --color-surface-highest: #DFE5F1;
  --color-on-surface: #07173F;       --color-on-surface-variant: #43506E;
  --color-outline: #737F9C;          --color-outline-variant: #C3CCE0;
  --color-error: #B32C00;
}
```

**Fuentes (`app/layout.tsx`):** `Fira_Sans`, `Overpass` y `Fira_Code` de `next/font/google`
con `variable: "--font-fira-sans"` etc.; Material Symbols Rounded con el `<link>` de Google Fonts.

**Mapa (`LossMap`):** `L.geoJSON` sin teselas de fondo (fondo sólido `surface-lowest`: más
rápido y funciona sin internet en la demo). Si se agregan teselas, incluir su atribución.

```ts
// src/lib/design/colors.ts · alerta de 5 niveles: idéntico a qgis/estilos/perdida_cacao.qml
export const LOSS_RAMP = ["#b2ffd8", "#fae61e", "#e67800", "#c80000", "#640000"] as const;
// Límite superior inclusivo, como el renderizador graduado de QGIS
export const lossClassIndex = (p: number) => (p <= 5 ? 0 : p <= 15 ? 1 : p <= 30 ? 2 : p <= 45 ? 3 : 4);
// Crítica: patrón SVG <pattern id="cr-hatch"> montado una vez en el layout (atoms/HatchDefs)
export const lossFill = (p: number) => (lossClassIndex(p) === 4 ? "url(#cr-hatch)" : LOSS_RAMP[lossClassIndex(p)]);

const style = (f: GeoJSON.Feature) => ({
  fillColor: p == null ? NO_DATA[theme] : lossFill(p),   // Leaflet escribe atributos SVG: sin var()
  fillOpacity: 1,
  color: theme === "mision" ? "#040C24" : "#232323",
  weight: 0.7,
});
// La selección se dibuja aparte (pane "seleccion"): halo de 6 px + trazo de 2,5 px.
```

Escala gráfica y flecha norte: `L.control.scale({ metric: true, imperial: false })` y un control propio
para el norte; SRC del mapa base: EPSG:4326 en los datos, EPSG:3857 en pantalla (Leaflet).

**Formato:** `new Intl.NumberFormat("es-EC")` → `41.000 t`, `USD 4,9 M`, `22,4 %`.

**Estado:** `scenario`, `province`, `selectedAreaId`, `theme` (igual que 04-frontend.md). El
escenario se refleja en la URL (`?escenario=nino&canton=…`) para compartir enlaces.

## 12. Exportación compatible con QGIS

Todo está en [`qgis/`](../qgis/README.md):

| Archivo | Para qué |
|---------|----------|
| `qgis/estilos/perdida_cacao.qml` / `.sld` | Leyenda de pérdida (graduado sobre `loss_pct`, alerta de 5 niveles; Crítica con `LinePatternFill`) |
| `qgis/estilos/zonas_2050.qml` / `.sld` | Matriz de zonas (categorizado sobre `zona_2050`) |
| `qgis/datos/cacao_perdida_EJEMPLO.gpkg` | 6 capas (5 escenarios + zonas) con el estilo guardado en `layer_styles`: QGIS las abre ya coloreadas. Datos ilustrativos. |
| `qgis/exportar_gpkg.py` | `write_styled_gpkg()` para el endpoint del backend |

**Endpoint propuesto:** `GET /api/v1/export?scenarios=…&format=gpkg|geojson|shp|sld&crs=4326|32717&level=canton|province`.
GeoPackage = un archivo con todas las capas y su estilo por defecto; GeoJSON/Shapefile = `.zip`
con un `.qml` del mismo nombre (QGIS lo aplica al abrir); SLD para GeoServer. Campos de ≤ 10
caracteres (`canton`, `provincia`, `escenario`, `loss_pct`, `loss_p10`, `loss_p90`, `clase`,
`zona_2050`, `fuente`) para que también sirvan en Shapefile. SRC por defecto EPSG:4326; opción
EPSG:32717 (UTM 17S) para medir y maquetar.

## 13. Accesibilidad (checklist)

- [ ] Contraste ≥ 4,5:1 en texto (≥ 3:1 en controles y bordes).
- [ ] Cada color de dato con número/nombre/ícono; botón "Ver como tabla" en el mapa.
- [ ] Nivel Crítico con rayado (no depende del color); `forced-colors` quita texturas de botones.
- [ ] Mapa navegable con teclado (lista de cantones equivalente) y `aria-label` en controles.
- [ ] Áreas táctiles ≥ 48 px; hoja inferior arrastrable y también con botón.
- [ ] Textos para productores en lenguaje simple; términos técnicos en "Ver más".
- [ ] `prefers-reduced-motion`: sin animación de transición del mapa.

## 14. Decisiones abiertas

| Tema | Propuesta | Decide |
|------|-----------|--------|
| Tema por defecto en la demo | Misión (oscuro) | Equipo front + presentación |
| Detalle en escritorio | Hoja lateral en vez de panel inferior | Equipo front |
| Capa "Riesgo de moniliasis" en Fase 1 | Mostrar si `disease_risk_monthly` está listo a tiempo | Datos/ETL |
| PWA sin conexión para campo | Hecha (fase 4 del rediseño, §15) | — |
| Endpoint `/export` (GeoPackage con estilo) | Fase 1 si el backend llega; si no, entregar el `.gpkg` estático de la demo | Backend |

## 15. Rediseño por fases (sistema atómico)

**Fase 1 · hecha (código + Figma).** Verde cacao como primario, alerta de 5 niveles IPC/SNGR,
semáforo de zonas, textura de botones y componentes reorganizados en `FRONT/src/components/`:

| Nivel | Componentes |
|-------|-------------|
| Átomos | `Icon`, `Button` (filled · tonal · outlined · text) · `IconButton`, `FilterChip`, `Badge`, `Swatch`, `Skeleton`, `HatchDefs`, `Logo` |
| Moléculas | `SegmentedButton`, `ScenarioSelector`, `LegendItem`, `AlertLevelChip`, `KpiTile`, `ClassDistribution`, `LossInterval`, `Dialog`, `CantonSearch`, `DataSourceChip` |
| Organismos | `TopAppBar`, `EnsoBanner`, `Navigation`, `ControlPanel`, `SummaryCard`, `TopCantons`, `MapLegend`, `LossMap`, `LossTable`, `AreaSheet`, `LossHero`, `FactorBars`, `MonthlyRiskChart`, `RequirementCheck`, `StrategyCards`, `LossRangeChart`, `ZoneMatrix`, `ExportDialog`, `AlertScale` |
| Plantillas / pantallas | `AppShell` / `MapScreen`, `CompareScreen`, `MethodologyScreen` |

**Textura de botones** (`globals.css`): relleno con brillo superior (degradado blanco 22 % → 0),
borde interior de 1 px arriba y sombra de elevación 1; al presionar el brillo se invierte y la
sombra pasa a interior. Hover y presionado usan la **capa de estado M3** (`.state-layer`: 8 % y
12 % del color del texto), no `brightness()`, para que se vean igual en verde, azul o neutro.
Con `forced-colors` se quitan las texturas y queda un borde.

**Fase 2 · gráficos interactivos (hecha en código; ver FRONT/src/components/README.md).** Apache ECharts 5 (Apache-2.0) con
`echarts-for-react` (MIT), cargado con `next/dynamic` solo en el panel del cantón y en Comparar.
Tema ECharts propio generado desde los tokens (verde cacao, series moniliasis/mazorca, escala de
alerta) en Misión y Campo; tooltip con crosshair, leyenda siempre visible, botón "Ver como tabla"
y `aria` del componente. Gráficos: riesgo mes a mes (área + línea, bandas de alerta de fondo),
factores (barras horizontales con valor), rango p10–p90 por escenario (barra de intervalo +
punto), distribución de cantones por nivel (barra apilada al 100 %), y Niño 1+2 / ONI desde
NOAA (línea con umbral ±0,5). Datos: la misma API (`/areas/{id}/detail`, `/compare`,
`/enso/current`) — no se llama a servicios externos desde el navegador.

**Fase 3 · plantillas (hecha en código: `/plantillas`).** Tarjetas para compartir (PNG 1080×1080 del cantón con su nivel de
alerta), ficha imprimible A4 para el técnico y portada del video, con la misma paleta; se pueden
armar como plantillas de marca en Canva a partir de las variables de Figma.

**Fase 4 · modo Campo sin conexión (hecha).** PWA instalable con service worker propio: páginas y
estáticos guardados, la API con «red primero y copia guardada», botón «Guardar sin conexión» por cantón
(5 escenarios) y aviso claro cuando se muestran datos guardados (sin red o con el backend caído). Detalle
en `FRONT/src/components/README.md`.

**Fase 5 · Mi finca (hecha).** Punto «Finca individual» de 06-fases: dibujar el lote, GPS o coordenadas →
hectáreas, cantón (`/areas/lookup`), pérdida del cantón llevada a la finca y clima del punto (`/point/climate`,
NASA POWER). Pendientes de esa lista (requieren datos/backend): observaciones de campo (`/observations` ya existe
en BACK), GBIF, ECOSTRESS y el asistente (`/areas/{id}/insights` y `/ask` ya existen en BACK).

**Ajuste de paleta (después de la fase 5).** Las superficies dejan el azul marino: **Misión = verde bosque
nocturno** (`surface #0B1F17`, `lowest #07120D`, `high #1A3528`, texto crema `#F2F5EC`) y **Campo = crema cálido**
(`surface #FAF7EF`, `high #E6E0D0`, tinta `#14261C`). Barra superior y banner ENSO en verde profundo
(Misión `#06140E`, Campo `#0B3D25`); el azul NASA queda solo en el logo y en la serie «moniliasis». Nuevo terciario
cacao (`#E39A6F` / `#9A4E24`). Contrastes: texto ≥ 4,7:1, texto principal 15,6:1 (Misión) y 14,8:1 (Campo).
Maqueta de referencia en Canva: https://canva.link/tmyze3o1uo8rgbr

**Mapa satelital 3D (hecho).** Vista «Satélite 3D» con MapLibre GL JS 5: globo terráqueo, fondos Sentinel-2 sin nubes
2024 (EOX/Copernicus), VIIRS del día y Blue Marble (NASA GIBS, la fuente de Worldview), relieve 3D (AWS Terrain
Tiles), columnas 3D de pérdida y mazorcas de cacao donde la aptitud es alta, coloreadas por zona 2050. Detalle y
licencias en `FRONT/src/components/README.md`.

**Rediseño con la plantilla Harvest + capas tipo Google Maps (hecho).** Paleta verde agrícola de TooEzra/green-tech,
encabezado claro, barra lateral con nombres, pantalla `/panel` y menos ruido visual (una fila de controles, menús en
vez de botones sueltos). En «Satélite 3D», botón *Capas* como Google Maps: tipo de mapa, detalles (lluvia,
vegetación, incendios, temperatura, aire de NASA GIBS) y herramienta *Medir*. Detalle en FRONT/src/components/README.md.
