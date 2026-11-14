-- =====================================================================
--  0009 — Vistas de cobertura: qué datos hay, de dónde vienen y qué falta.
--  Se recalculan solas: no hay que mantenerlas al cargar datos nuevos.
-- =====================================================================

-- ¿Qué variables del catálogo tienen datos cargados?
create view public.v_variable_coverage with (security_invoker = true) as
select v.id as variable_id, v.name, v.unit, v.source_id, v.temporal_res,
       coalesce(s.n_rows, 0)  as rows_series,
       coalesce(s.n_areas, 0) as areas_series,
       s.first_month, s.last_month,
       coalesce(c.n_rows, 0)  as rows_scenarios,
       case when coalesce(s.n_rows, 0) + coalesce(c.n_rows, 0) > 0 then 'cargada' else 'pendiente' end as status
  from public.variables v
  left join (select variable_id, count(*) n_rows, count(distinct area_id) n_areas,
                    min(month_date) first_month, max(month_date) last_month
               from public.area_monthly_series group by 1) s on s.variable_id = v.id
  left join (select variable_id, count(*) n_rows
               from public.area_scenario_climate group by 1) c on c.variable_id = v.id;
comment on view public.v_variable_coverage is 'Por variable del catálogo: filas cargadas, áreas, rango de meses y estado (cargada / pendiente).';

-- ¿Qué tan completo está cada territorio?
create view public.v_area_coverage with (security_invoker = true) as
select a.id as area_id, a.kind, a.name, p.name as parent_name, a.region,
       (a.inec_dpa_code is not null)  as has_dpa,
       (sf.area_id is not null)       as has_terrain,
       (sf.soil_ph is not null)       as has_soil,
       coalesce(h.n_years, 0)         as climate_years,
       h.first_year, h.last_year,
       coalesce(ps.real_years, 0)       as production_real_years,
       coalesce(ps.synthetic_years, 0)  as production_synthetic_years,
       (e.area_id is not null)        as has_exposure,
       coalesce(lp.n, 0)              as predictions
  from public.areas a
  left join public.areas p on p.id = a.parent_id
  left join public.area_static_features sf on sf.area_id = a.id
  left join (select area_id, count(distinct extract(year from month_date)) n_years,
                    min(extract(year from month_date))::int first_year, max(extract(year from month_date))::int last_year
               from public.area_monthly_hazard group by 1) h on h.area_id = a.id
  left join (select area_id,
                    count(*) filter (where source_id <> 'seed_sintetico') real_years,
                    count(*) filter (where source_id =  'seed_sintetico') synthetic_years
               from public.crop_production_stats group by 1) ps on ps.area_id = a.id
  left join (select distinct area_id from public.crop_exposure) e on e.area_id = a.id
  left join (select area_id, count(*) n from public.loss_predictions group by 1) lp on lp.area_id = a.id
 where a.kind <> 'field';
comment on view public.v_area_coverage is 'Por territorio: código DPA, terreno, suelo, años de clima, años de producción reales/sintéticos, exposición y predicciones.';

-- ¿Qué producción es real y cuál sintética, año por año?
create view public.v_production_provenance with (security_invoker = true) as
select year, source_id,
       (source_id <> 'seed_sintetico') as is_real,
       count(*) as n_areas,
       round(sum(production_t)) as production_t
  from public.crop_production_stats
 group by year, source_id;
comment on view public.v_production_provenance is 'Producción de cacao por año y fuente; is_real = false para el seed sintético.';
