# KittyProgram — CacaoResiliente

Herramienta de apoyo a la decisión para el cacao ecuatoriano frente a El Niño y el cambio
climático, con datos de la NASA. Reto **Field Shift: Adapting Farms with NASA Data** —
NASA Space Apps Challenge 2026.

## La pregunta

> **¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades
> asociadas a El Niño, hoy y con el clima de 2050?**

**Problema:** El Niño trae lluvias extremas y humedad que disparan la moniliasis y la mazorca
negra, y el cambio climático saca zonas del rango óptimo del cacao (21–32 °C, 1 200–3 000 mm);
el productor pierde cosechas e invierte a más de 25 años sin saber cuánto arriesga ni dónde.

**Solución:** cruzar los requerimientos del cacao (ECOCROP) con un índice de clima favorable a
enfermedades (NASA GPM, SMAP, MODIS, SRTM + ERA5-Land), entrenar un modelo con la producción
real (ESPAC/INEC) y El Niño (NOAA), estimar la pérdida por cantón en t y USD, y recomendar la
estrategia de manejo que más la reduce.

**Contexto:** NOAA CPC reporta un **El Niño fuerte en curso** (ONI ASO-2026 = +2.46;
Niño 1+2 en octubre 2026 = +5.25 °C).

## Fases

| Fase | Responde |
|------|----------|
| **1** | Pérdida por cantón en año normal vs año Niño (hoy) |
| **2** | Lo mismo con el clima de 2041–2060 (CMIP6) + matriz de zonas |
| 3 | Finca individual, observaciones de campo, ECOSTRESS |

## Contenido

| Ruta | Qué es |
|------|--------|
| [`docs/`](docs/README.md) | **Plan del proyecto**: propuesta, base de datos, backend, frontend, modelo, fases |
| [`docs/APIS-DATOS.md`](docs/APIS-DATOS.md) | **APIs para sacar los datos** (probadas) |
| [`supabase/migrations/`](supabase/migrations) | Esquema Supabase. `0005_cacaoresiliente.sql` = esquema del proyecto |
| [`BACK/docs/`](BACK/docs/README.md) | Documentación técnica base del backend (v1) |
| [`BACK/.env.example`](BACK/.env.example) | Variables de entorno (sin secretos) |
| [`BACK/nasa_data/`](BACK/docs/08-datos-nasa-equipo.md) | Módulo Python para descargar series NASA (GEE + POWER) a CSV |
| [`ml/`](ml/README.md) | Modelo predictivo de pérdida de cacao (ETL, features, entrenamiento, API) |

## Aplicar la base de datos

En Supabase → SQL Editor, en orden: `0001_init.sql` → `0002_fk_indexes.sql` →
`0003_field_rpc.sql` → `0004_more_sources.sql` → `0005_cacaoresiliente.sql` → `0006_revision.sql`
(o `supabase db push`).
