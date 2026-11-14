-- Índices para las claves foráneas (recomendación del linter de Supabase).
create index if not exists analysis_runs_requested_by_idx     on public.analysis_runs (requested_by);
create index if not exists area_climatology_variable_idx      on public.area_climatology (variable_id);
create index if not exists area_monthly_series_variable_idx   on public.area_monthly_series (variable_id);
create index if not exists expert_reviews_reviewer_idx        on public.expert_reviews (reviewer_id);
create index if not exists expert_reviews_strategy_idx        on public.expert_reviews (strategy_id);
create index if not exists field_current_rotation_crop_idx    on public.field_current_rotation (crop_id);
create index if not exists variables_source_idx               on public.variables (source_id);
