# KittyProgram

Base de datos y documentación del backend de **AgroRotación UIDE** — herramienta de apoyo
a la decisión para rotación de cultivos con datos satelitales de la NASA
(reto *Field Shift: Adapting Farms with NASA Data*, NASA Space Apps 2026).

## Contenido

| Ruta | Qué es |
|------|--------|
| [`supabase/migrations/`](supabase/migrations) | Esquema de Supabase (Postgres + PostGIS): 13 tablas, RLS, semilla de fuentes/variables NASA, RPC de fincas |
| [`BACK/docs/`](BACK/docs/README.md) | Documentación del backend FastAPI: arquitectura, configuración, base de datos, contrato del API CRUD, guía de implementación y caché NASA |
| [`BACK/.env.example`](BACK/.env.example) | Variables de entorno necesarias (sin secretos) |

## Aplicar la base de datos

En Supabase → **SQL Editor**, ejecutar en orden:

1. `supabase/migrations/0001_init.sql`
2. `supabase/migrations/0002_fk_indexes.sql`
3. `supabase/migrations/0003_field_rpc.sql`

o con la CLI: `supabase db push`.

Empieza por [`BACK/docs/README.md`](BACK/docs/README.md).
