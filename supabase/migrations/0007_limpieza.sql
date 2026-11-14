-- =====================================================================
--  0007 — Limpieza: se eliminan las tablas de la v1 (rotación de cultivos)
--         y se cierra el acceso público de las tablas internas.
-- =====================================================================
--  Tablas que ya no usa CacaoResiliente (estaban vacías):
--    analysis_runs, rotation_strategies, expert_reviews   → reemplazadas por
--      loss_predictions, strategy_evaluations y strategy_reviews
--    area_climatology                                     → reemplazada por
--      area_scenario_climate y area_monthly_series
--    field_current_rotation, field_priorities             → eran de rotación
--  Se conserva field_profiles (datos de la finca, Fase 3) y las funciones
--  create_field / update_field_geom.
-- =====================================================================

-- Orden: primero las hijas (expert_reviews → rotation_strategies → analysis_runs).
drop table public.expert_reviews;
drop table public.rotation_strategies;
drop table public.analysis_runs;
drop table public.area_climatology;
drop table public.field_current_rotation;
drop table public.field_priorities;

-- Tablas internas: solo el backend (service_role) las lee y escribe.
-- Sin política ni privilegios, dejan de exponerse en la API pública.
drop policy "public read" on public.etl_runs;
drop policy "public read" on public.training_samples;
revoke all on public.etl_runs         from anon, authenticated;
revoke all on public.training_samples from anon, authenticated;

comment on table public.etl_runs         is 'Interna: bitácora de cargas. Solo backend.';
comment on table public.training_samples is 'Interna: copia del dataset de entrenamiento. Solo backend.';
