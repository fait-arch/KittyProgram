# FRONT — CacaoResiliente (propuesta 2, SvelteKit)

SPA en **SvelteKit 3 + Svelte 5 (runes) + MapLibre 6**. Gráficos en SVG propio (sin librerías).

```bash
cd FRONT && npm install
cp .env.example .env        # opcional: Supabase para login de técnicos
npm run dev                 # http://0.0.0.0:8767  (visible en la red local)
```

El backend debe correr en `:8000` (`cd BACK && venv/bin/uvicorn run:app --port 8000`).
Vite reenvía `/api` y `/health` → `BACKEND_URL` (defecto `http://localhost:8000`), así que no hace falta CORS
ni exponer el backend. Producción: `npm run build` → `build/` estático (fallback `index.html`) y
`VITE_API_BASE=https://api…` si la API está en otro dominio.

> SvelteKit 3: la config va en `vite.config.ts` (no hay `svelte.config.js`) y `$lib` pasó a ser `#lib`
> (`imports` en `package.json`).

## Pantalla

Mapa a pantalla completa + 3 piezas flotantes, nada más:

| Zona | Qué muestra | Endpoints |
|------|-------------|-----------|
| Barra superior | Escenario, El Niño ahora, menú (cultivo, provincia, estado API) | `/scenarios` `/enso/current` `/crops` `/areas?kind=province` `/health` |
| Mapa | Pérdidas por cantón o zonas 2050 · observaciones · "Mi finca" · clic fuera = punto libre | `/losses/geojson` · `/areas/geojson` + `/zones` · `/observations` · `/areas/lookup` |
| Tarjeta izquierda | Totales, vs. normal, más afectados, ranking, buscador | `/losses/summary` `/losses` `/areas?has_crop=` |
| Panel del cantón → **Resumen** | Pérdida + rango, factores, ECOCROP, terreno | `/areas/{id}/detail` `/areas/{id}` |
| → **Qué hacer** | Estrategias reordenadas por prioridades (sliders) | `/areas/{id}/strategies?priorities=` |
| → **Asistente IA** | Diagnóstico + chat | `/areas/{id}/insights` `POST /areas/{id}/ask` |
| → **Enfermedades** | Mapa de calor mes × patógeno, calendario, historia vs ONI | `/areas/{id}/risk` `/crops/{c}/phenology` `/areas/{id}/risk/history` `/crops/{c}/pathogens` |
| → **Clima** | Escenario vs normal, anomalías satelitales, extremos | `/areas/{id}/climate` `/areas/{id}/series` `/areas/{id}/hazards` |
| → **Escenarios** | 6 escenarios lado a lado + aptitud | `/compare` `/areas/{id}/suitability` |
| → **Simular** | What-if lluvia / temperatura / Niño | `POST /predict` |
| → **Campo** | Reportes + formulario (login Supabase) | `/observations` `POST /observations` |
| Panel punto libre | Clima NASA POWER + chequeo cacao | `/point/climate` `/areas/lookup` |
| Modal El Niño | ONI / Niño 1+2, eventos, años | `/enso/current` `/enso/history` `/enso/events` `/enso/years` |
| Modal Metodología | Modelo, fuentes, variables, cultivo, estrategias, escenarios | `/meta` `/crops` `/crops/{c}/requirements` `/crops/{c}/pathogens` `/strategies` `/scenarios` |
| Modal Estado | Salud y acciones admin | `/health` `POST /admin/cache/clear` `POST /admin/model/reload` |

Las **37 rutas** del contrato (`docs/backend/02-endpoints.md`) están en `src/lib/api.ts` y todas se usan.

## Estructura

```
src/lib/api.ts            cliente (1 función = 1 endpoint) + login Supabase REST
src/lib/state.svelte.ts   estado global (escenario, selección, prioridades, sesión)
src/lib/components/       TopBar, MapView, Overview, AreaPanel, modales, Async, Segmented
src/lib/tabs/             una pestaña del panel por archivo
src/lib/charts/           Chart (línea/barra/área, 2 ejes, bandas) y RiskHeatmap
```
