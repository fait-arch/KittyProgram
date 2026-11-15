-- 0010 — Campos del modelo de ML en las predicciones (cacao_loss_v1, rama beltranfuego)
--
-- evidence               'validado_nacional' | 'indice_subnacional_no_validado' | 'proyeccion_cmip6_no_validada'
-- extrapolated           el clima del escenario es más extremo que cualquier año de entrenamiento
-- prob_loss_gt20         probabilidad (0–1) de perder más del 20 % (cuando el modelo la entregue)
-- inherited_from_area_id el cantón usa el índice de esta provincia (el modelo se entrena por provincia)
--
-- v_loss_map se recrea agregando estas columnas AL FINAL (create or replace no permite reordenar).

alter table public.loss_predictions
  add column if not exists evidence text
    check (evidence in ('validado_nacional', 'indice_subnacional_no_validado', 'proyeccion_cmip6_no_validada')),
  add column if not exists extrapolated boolean not null default false,
  add column if not exists prob_loss_gt20 numeric check (prob_loss_gt20 between 0 and 1),
  add column if not exists inherited_from_area_id uuid references public.areas(id) on delete set null;

-- Si la columna ya existía (carga anterior), se rehace el check para aceptar las proyecciones 2050 del modelo
alter table public.loss_predictions drop constraint if exists loss_predictions_evidence_check;
alter table public.loss_predictions add constraint loss_predictions_evidence_check
  check (evidence in ('validado_nacional', 'indice_subnacional_no_validado', 'proyeccion_cmip6_no_validada'));

comment on column public.loss_predictions.evidence is 'Nivel de validación: nacional validado, índice por zona no validado o proyección CMIP6 2050 no validada.';
comment on column public.loss_predictions.extrapolated is 'true si el clima del escenario sale del rango de entrenamiento.';
comment on column public.loss_predictions.prob_loss_gt20 is 'Probabilidad de perder más del 20 % (0–1).';
comment on column public.loss_predictions.inherited_from_area_id is 'Provincia cuyo índice usa el cantón.';

create index if not exists loss_predictions_inherited_idx on public.loss_predictions (inherited_from_area_id);

create or replace view public.v_loss_map with (security_invoker = true) as
select a.id            as area_id,
       a.name,
       a.kind,
       a.region,
       a.inec_dpa_code,
       p.name          as province,
       a.area_ha,
       a.geom_simplified as geom,
       lp.crop_id,
       lp.scenario_id,
       lp.loss_pct, lp.loss_pct_low, lp.loss_pct_high,
       lp.exposed_ha, lp.loss_t, lp.loss_usd,
       lp.risk_class, lp.top_factors,
       mv.name         as model_name,
       lp.evidence,
       lp.extrapolated,
       lp.prob_loss_gt20,
       ip.name         as inherited_from
  from public.loss_predictions lp
  join public.model_versions mv on mv.id = lp.model_version_id and mv.is_active
  join public.areas a           on a.id  = lp.area_id
  left join public.areas p      on p.id  = a.parent_id
  left join public.areas ip     on ip.id = lp.inherited_from_area_id;
comment on view public.v_loss_map is 'Una fila por área × escenario con todo lo que necesita el mapa (solo el modelo activo).';
