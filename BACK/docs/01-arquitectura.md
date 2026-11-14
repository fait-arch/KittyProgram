# 1. Arquitectura

## Vista general

```
┌──────────────────────┐   JWT del usuario    ┌───────────────────────────┐
│  Frontend (Next.js)  │ ───────────────────► │  Backend (FastAPI)        │
│  · mapa Leaflet      │ ◄─────────────────── │  · routers  (HTTP)        │
│  · login Supabase    │      JSON            │  · services (lógica)      │
└──────────┬───────────┘                      │  · repositories (BD)      │
           │ login (supabase-js)              └──────┬──────────────┬─────┘
           ▼                                         │              │
┌──────────────────────┐   lee/escribe (RLS o        │              │ calcula si
│  Supabase            │ ◄─── service_role) ─────────┘              │ no está en caché
│  · Auth              │                                            ▼
│  · Postgres+PostGIS  │                        ┌───────────────────────────────────┐
└──────────────────────┘                        │ Fuentes NASA                      │
                                                │ · Google Earth Engine (GPM, SMAP, │
                                                │   MODIS, GRACE, SRTM)             │
                                                │ · NASA POWER API (clima diario)   │
                                                │ · NASA Earthdata (ECOSTRESS)      │
                                                └───────────────────────────────────┘
```

## Responsabilidades

| Capa | Hace | No hace |
|------|------|---------|
| **Frontend** | Login, dibujar finca, mostrar mapa/resultados | Nunca habla con GEE ni usa la `service_role` |
| **Backend – routers** | Validar entrada (Pydantic), autenticar, devolver HTTP | Lógica de negocio |
| **Backend – services** | Cálculos (GEE, POWER, motor de rotación) | Acceso directo a la BD |
| **Backend – repositories** | Leer/escribir en Supabase | Cálculos |
| **Supabase** | Guardar datos, Auth, aplicar RLS | Cálculos satelitales |
| **GEE / POWER / Earthdata** | Fuente de datos satelitales | Guardar estado de la app |

## Dos clientes de Supabase en el backend

| Cliente | Clave | Cuándo |
|---------|-------|--------|
| **Cliente de usuario** | `anon key` + JWT del usuario | CRUD de datos del agricultor (fincas, prioridades, rotación). **RLS** garantiza que solo toque lo suyo. |
| **Cliente de servicio** | `service_role key` | Escribir caché NASA, resultados de análisis y catálogos. Salta RLS: usarlo solo en código del servidor. |

## Flujo principal: "comparar rotaciones de mi finca"

1. El agricultor inicia sesión (Supabase Auth) y dibuja su finca → `POST /api/v1/fields`.
2. Indica su rotación actual y prioridades → `PUT /fields/{id}/rotation`, `PUT /fields/{id}/priorities`.
3. Pide la comparación → `POST /api/v1/fields/{id}/rotation-runs`.
4. El backend busca el perfil climático en caché (`area_climatology`); si no existe, lo calcula
   en GEE/POWER y lo guarda ([ver caché](06-cache-nasa.md)).
5. El motor de rotación puntúa la rotación actual + alternativas y guarda el resultado
   (`analysis_runs` + `rotation_strategies`).
6. El frontend muestra calendario, puntajes y la explicación (por qué, evidencia, riesgos).
