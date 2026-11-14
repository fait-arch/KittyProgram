# CacaoResiliente — documentación

> **¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades
> asociadas a El Niño, hoy y con el clima de 2050?**

| # | Documento | Contenido |
|---|-----------|-----------|
| 1 | [Propuesta](01-propuesta.md) | Problema, pregunta, solución, objetivos, requerimientos del cacao |
| 2 | [Base de datos](02-base-de-datos.md) | Todas las variables que controlamos, tablas, vista de entrenamiento, RLS |
| 3 | [Backend](03-backend.md) | ETL, API REST, estructura de carpetas, cómo se corre |
| 4 | [Frontend](04-frontend.md) | Pantallas, componentes, qué endpoint usa cada uno |
| 5 | [Modelo predictivo](05-modelo-predictivo.md) | Target, features, modelos, validación, incertidumbre, código |
| 6 | [Fases y tareas](06-fases.md) | Fase 1 (El Niño hoy) → Fase 2 (2050) → Fase 3 (extras) |
| — | [**APIs y fuentes de datos**](APIS-DATOS.md) | Endpoints, IDs de Earth Engine y código para sacar cada dato |
| — | [**Backend integrador**](backend/README.md) | Contrato de endpoints, integración con ML, Supabase, pendientes y decisiones |

Migración de base de datos: [`supabase/migrations/0005_cacaoresiliente.sql`](../supabase/migrations/0005_cacaoresiliente.sql).
Documentación técnica base (v1, rotación de cultivos): [`BACK/docs/`](../BACK/docs/README.md).
