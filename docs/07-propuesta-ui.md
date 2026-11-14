# 7. Propuesta UI/UX — Material 3 × NASA Space Apps

> Complementa [04-frontend.md](04-frontend.md) (pantallas, componentes y endpoints). Aquí se
> define **cómo se ve y se usa**: sistema de diseño, pantallas, guion de la demo e
> implementación. Lienzo con las 7 pantallas (privado hasta compartirlo):
> <https://claude.ai/artifact/4h4wX7wh1Z6DvDD7uPxuFX>

**Base:** estructura, componentes y accesibilidad de **Material Design 3** (Google) +
color y tipografía de la **guía de marca NASA Space Apps 2026**. No se usa la insignia de la
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
| Electric Blue | `#0042A6` | Primary en Campo; inicio del degradado oficial |
| Neon Blue | `#0960E1` | Enlaces; zona "segura" en Campo |
| Blue Yonder | `#2E96F5` | Primary en Misión; series y barras de datos |
| Neon Yellow | `#EAFE07` | **Único acento interactivo** (botón clave y enlaces en Misión). Nunca fondo ni titular. |
| Rocket Red | `#E43700` | Zona «crítica» (Campo) y alertas. Nunca fondo; siempre con texto o ícono. |
| Martian Red | `#8E1100` | `error-container` (Misión) |
| White | `#FFFFFF` | Superficie de Campo; texto sobre azules |

Reglas de la guía que respetamos: texto largo solo sobre Deep Blue, Electric Blue o blanco;
contraste ≥ 4,5:1; degradado Electric Blue → Deep Blue a 45° (solo en el banner ENSO y
portadas); regla 60-30-10.

## 4. Roles de color Material 3

| Rol M3 | Misión (oscuro) | Campo (claro) |
|--------|-----------------|---------------|
| `primary` / `on-primary` | `#2E96F5` / `#04122F` | `#0042A6` / `#FFFFFF` |
| `primary-container` / `on-…` | `#0042A6` / `#DCE8FF` | `#D9E5FF` / `#07173F` |
| `secondary-container` (selección) | `#1E3A78` | `#DDE6F7` |
| `tertiary` (acento) | `#EAFE07` | `#0960E1` (enlace) |
| `surface` | `#07173F` | `#F8FAFF` |
| `surface-container-lowest` | `#040C24` | `#FFFFFF` |
| `surface-container-low` | `#0A1C48` | `#F2F5FC` |
| `surface-container` | `#0E2252` | `#ECF0F9` |
| `surface-container-high` | `#13295D` | `#E6EBF5` |
| `surface-container-highest` | `#1A3268` | `#DFE5F1` |
| `on-surface` / `on-surface-variant` | `#EAF0FF` / `#B3C1E0` | `#07173F` / `#43506E` |
| `outline` / `outline-variant` | `#6F82AE` / `#2A3F72` | `#737F9C` / `#C3CCE0` |
| `error` / `error-container` | `#FF8A6B` / `#8E1100` | `#B32C00` / `#FFDAD2` |

Contraste medido (WCAG 2): texto principal 15,3:1 (Misión) y 16,7:1 (Campo); texto
secundario ≥ 6,7:1; Neon Yellow sobre Deep Blue 15,5:1; Blue Yonder sobre Deep Blue 5,6:1.

## 5. Colores de datos

**Pérdida estimada: ColorBrewer YlOrRd, 4 clases (de amarillo a rojo, patrón QGIS):**

| Clase | Rango `loss_pct` | Color (app y QGIS) |
|-------|------------------|--------------------|
| Baja | 0 – 5 % | `#ffffb2` |
| Moderada | 5 – 15 % | `#fecc5c` |
| Alta | 15 – 30 % | `#fd8d3c` |
| Muy alta | 30 – 100 % | `#e31a1c` |

Es la rampa graduada clásica de QGIS (*Graduado › ColorBrewer › YlOrRd*): la misma en los dos
temas, en la app, en el `.qml` y en el `.sld`, para que una captura de la app y una lámina de
QGIS se lean igual. Reglas de QGIS que seguimos: límite superior inclusivo (5,0 % = Baja),
leyenda ascendente con rótulos `0 – 5`, borde `#232323` de 0,26 mm (el borde oscuro separa la
clase amarilla de un fondo claro), y en el mapa: grilla de coordenadas, escala gráfica, flecha
norte y SRC. Selección del cantón: borde blanco (Misión) o Electric Blue (Campo), no amarillo,
para no confundirse con la rampa. Fuera del alcance (Sierra/Amazonía): superficie neutra.

**Matriz de zonas 2050 (divergente azul ↔ rojo, siempre con nombre + ícono):**

| Zona | Cuadrante | Ícono | Misión | Campo |
|------|-----------|-------|--------|-------|
| Segura | aptitud alta · riesgo bajo | `verified` | `#2e96f5` | `#0760e1` |
| Manejo | aptitud alta · riesgo alto | `handyman` | `#315a97` | `#9dc1ee` |
| Transición | aptitud baja · riesgo bajo | `swap_horiz` | `#994920` | `#f0ad7f` |
| Crítica | aptitud baja · riesgo alto | `report` | `#fb784f` | `#e43700` |

Azul/naranja en vez de verde/rojo: todos los pares se distinguen con protanopía y
deuteranopía (ΔE ≥ 15). Los tonos medios quedan bajo 3:1 contra el fondo, por eso la capa
siempre lleva leyenda con nombres y vista de tabla.

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
// ColorBrewer YlOrRd · 4 clases: idéntico a qgis/estilos/perdida_cacao.qml
export const LOSS = ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"] as const;
const NO_DATA = { mision: "#0E2252", campo: "#DFE5F1" } as const; // Leaflet escribe atributos SVG: sin var()
// Límite superior inclusivo, como el renderizador graduado de QGIS
export const lossClass = (p: number) => (p <= 5 ? 0 : p <= 15 ? 1 : p <= 30 ? 2 : 3);

const style = (f: GeoJSON.Feature) => {
  const p = lossById.get(f.properties!.id);
  const selected = f.properties!.id === selectedAreaId;
  return {
    fillColor: p == null ? NO_DATA[theme] : LOSS[lossClass(p)],
    fillOpacity: 1,
    color: selected ? (theme === "mision" ? "#FFFFFF" : "#0042A6") : (theme === "mision" ? "#040C24" : "#232323"),
    weight: selected ? 3 : 0.7,
  };
};
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
| `qgis/estilos/perdida_cacao.qml` / `.sld` | Leyenda de pérdida (graduado YlOrRd 4 clases sobre `loss_pct`) |
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
| PWA sin conexión para campo | Fase 3 | — |
| Endpoint `/export` (GeoPackage con estilo) | Fase 1 si el backend llega; si no, entregar el `.gpkg` estático de la demo | Backend |
