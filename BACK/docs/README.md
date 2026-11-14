# Documentación del backend — AgroRotación UIDE

Backend en **FastAPI** que combina datos satelitales de la **NASA** (vía Google Earth Engine,
NASA POWER y Earthdata) con una base de datos **Supabase (Postgres + PostGIS)** para ayudar
a agricultores a comparar estrategias de rotación de cultivos.

> Proyecto para el reto *Field Shift: Adapting Farms with NASA Data* — NASA Space Apps 2026.

## Índice

| # | Documento | Para qué sirve |
|---|-----------|----------------|
| 1 | [Arquitectura](01-arquitectura.md) | Cómo encajan frontend, backend, Supabase y las fuentes NASA |
| 2 | [Configuración](02-configuracion.md) | Variables de entorno, credenciales y cómo levantar el backend |
| 3 | [Base de datos](03-base-de-datos.md) | Tablas, relaciones, seguridad (RLS) y migraciones |
| 4 | [API CRUD](04-api-crud.md) | Contrato de cada endpoint: rutas, cuerpos, respuestas y errores |
| 5 | [Guía de implementación del CRUD](05-guia-implementacion.md) | Estructura de carpetas y código base para implementar los endpoints |
| 6 | [Caché de datos NASA](06-cache-nasa.md) | Cómo se calculan y guardan los datos satelitales sin gastar cuota |

## Inicio rápido

```bash
cd BACK
python -m venv venv                 # usar Python 3.12 (3.14 no tiene wheels de pydantic 2.8)
venv\Scripts\activate               # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # y rellenar (ver 02-configuracion.md)
earthengine authenticate
uvicorn run:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva (Swagger): http://localhost:8000/docs

## Estado actual

| Pieza | Estado |
|-------|--------|
| Análisis de aptitud (banano) con GEE | ✅ Implementado (`/api/v1/analysis`) |
| Territorio (provincias/cantones) | ✅ Implementado (`/api/v1/territory`) |
| Chat de capas por palabras clave | ✅ Implementado (`/api/v1/chat`) |
| Esquema Supabase (13 tablas + RLS) | ✅ Aplicado (`supabase/migrations/`) |
| CRUD de cultivos, fincas, rotación, prioridades | 📝 Especificado en estos docs, pendiente de código |
| Perfil climático NASA por finca + caché | 📝 Especificado, pendiente de código |
| Motor de comparación de rotaciones | 📝 Especificado, pendiente de código |
