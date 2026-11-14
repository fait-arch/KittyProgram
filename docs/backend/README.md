# Backend integrador — CacaoResiliente

> Rama: `emilio/backend` · Responsable: backend integrador
> Base: plan del proyecto en [`docs/`](../README.md) (rama `diego/supabase-docs`).

Este backend es la **pieza que une todo**: lee lo que el ETL y el modelo dejan en Supabase,
agrega lo que hace falta y lo entrega al frontend en un solo contrato estable.

```
 ETL / Datos (compañero de datos)        ML (compañero del modelo)
 GEE · NOAA · ESPAC · POWER                train.py · predict.py
            │ escribe                          │ escribe / publica artefacto
            ▼                                  ▼
        ┌──────────────────── Supabase (Postgres + PostGIS + Storage) ────────────────────┐
        └─────────────────────────────────────┬───────────────────────────────────────────┘
                                              │ lee (anon) · escribe solo lo propio (service)
                                    ┌─────────▼─────────┐
                                    │ FastAPI (nosotros)│──► NASA POWER (proxy con caché)
                                    │  /api/v1/...      │──► modelo .joblib (what-if en vivo)
                                    └─────────▲─────────┘
                                              │ JSON
                                          Frontend
```

## La pregunta que respondemos

> **¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades
> asociadas a El Niño, hoy y con el clima de 2050?**

El backend se diseña **agnóstico al cultivo** (`crop_id` en todas las rutas, `cacao` por
defecto) por si el equipo agrega otros cultivos sin rehacer la API.

## Documentos

| # | Documento | Para quién | Contenido |
|---|-----------|------------|-----------|
| 1 | [Arquitectura](01-arquitectura.md) | Todos | Capas, responsabilidades, qué es precalculado y qué es en vivo, caché |
| 2 | [**Endpoints**](02-endpoints.md) | Front + backend | Contrato completo de cada ruta: parámetros, respuesta, tablas que lee |
| 3 | [Integración del modelo ML](03-integracion-ml.md) | ML + backend | Contrato con el modelo: tablas, nombres de features, artefacto, predicción en vivo |
| 4 | [Supabase y configuración](04-supabase-config.md) | Datos + backend | Clientes, consultas por endpoint, RPC que faltan, MCP, `.env`, cómo correr |
| 5 | [Pendientes y decisiones](05-pendientes.md) | Todos | Inconsistencias encontradas en el repo, decisiones abiertas, tareas por persona |

## Cómo continuar (orden recomendado)

1. Leer [02-endpoints.md](02-endpoints.md) — es el contrato; el front puede empezar con *mocks*.
2. Decisiones tomadas: [05-pendientes.md](05-pendientes.md) (§ Decisiones).
3. La BD ya está desplegada por Datos (`0001 → 0006`). **El backend no modifica el esquema**:
   solo lee (y escribe observaciones de campo como el usuario, con RLS).
4. Orden de implementación: **sistema → catálogos → ENSO → áreas/GeoJSON → pérdidas →
   detalle → estrategias → insights IA** (todo lectura). Después what-if y Fase 2.
5. Mientras el ETL/ML no llenen las tablas, `DATA_SOURCE=mock` devuelve datos de prueba
   con el mismo formato que la respuesta real.

## Estado

| Pieza | Estado |
|-------|--------|
| Contrato de endpoints | 📝 Este documento |
| Esquema Supabase (0001–0006) | ✅ Desplegado (Diego) |
| Código FastAPI (`BACK/app/`), 36 rutas | ✅ Funciona en `DATA_SOURCE=mock`; 50 tests |
| Insights y recomendaciones con IA (DeepSeek) | ✅ Implementado; falta `DEEPSEEK_API_KEY` |
| Conexión a Supabase real (`chjgktgkilxjuwuuekah`) | ✅ Probada: catálogos con datos; territorio, ENSO y pérdidas vacíos hasta el ETL (ENSO cae a NOAA en vivo) |
| Porcentajes/costos de estrategias | ⚠ **Supuestos por validar**: ver [05 § Supuestos](05-pendientes.md) |
| ETL que llena tablas | ⏳ Datos |
| Modelo y `loss_predictions` | ⏳ ML |

## Arrancar en 1 minuto

```bash
cd BACK && uv venv --python 3.12 venv && uv pip install --python venv/bin/python -r requirements.txt
cp .env.example .env && venv/bin/uvicorn run:app --reload --host 0.0.0.0 --port 8000
# http://localhost:8000/docs
```

## Reglas del backend

1. **La API no calcula en vivo con GEE.** Todo lo pesado está precalculado en Supabase.
2. Lo único "en vivo": NASA POWER por punto (con caché), el *what-if* con el modelo cargado
   en memoria (milisegundos), las estrategias (se calculan al vuelo con `strategy_effects`) y
   los insights de IA (DeepSeek, con caché).
3. Toda respuesta con resultados lleva `disclaimer` y la versión del modelo usada.
4. Secretos solo en `BACK/.env` (nunca en el repo). Ver [04](04-supabase-config.md).
