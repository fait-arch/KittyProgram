-- =====================================================================
--  0006 — Correcciones de la revisión del esquema CacaoResiliente
-- =====================================================================
--  1. areas: código INEC (DPA), nombre normalizado, región, geometría
--     simplificada para el mapa.
--  2. variables.temporal_res + disease_thresholds.resolution: los umbrales
--     se evalúan sobre valores DIARIOS aunque la serie se guarde mensual.
--  3. area_monthly_hazard: peligros climáticos por área y mes (una sola
--     vez), fuera de disease_risk_monthly.
--  4. crop_phenology: etapas del cultivo y ventana de riesgo por región.
--  5. v_enso_year_class: regla única para clasificar cada año (Niño/Niña).
--  6. strategy_effects: efecto de cada estrategia por objetivo.
--  7. v_loss_map: una sola vista para el mapa del frontend.
--  8. etl_runs: registro de cargas.
--  9. Comentarios: crop_requirements es la fuente de verdad del cultivo.
--  Todas las tablas afectadas están vacías: no hay pérdida de datos.
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- 1. ÁREAS
-- ─────────────────────────────────────────────────────────────────────
alter table public.areas
  add column inec_dpa_code  text,
  add column region         text check (region in ('costa','sierra','amazonia','insular')),
  add column name_key       text generated always as
             (lower(translate(name, 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun'))) stored,
  add column geom_simplified extensions.geometry(MultiPolygon, 4326) generated always as
             (extensions.st_multi(extensions.st_simplifypreservetopology(geom, 0.002))) stored;

create unique index areas_inec_dpa_idx  on public.areas (inec_dpa_code) where inec_dpa_code is not null;
create index        areas_name_key_idx  on public.areas (kind, name_key);

comment on column public.areas.inec_dpa_code   is 'Código DPA del INEC (provincia: 2 dígitos, cantón: 4). Clave para cruzar con ESPAC.';
comment on column public.areas.name_key        is 'Nombre en minúsculas y sin tildes, para cruzar GAUL ("Los Rios") con INEC ("Los Ríos").';
comment on column public.areas.region          is 'Región natural; decide la ventana de riesgo (crop_phenology).';
comment on column public.areas.geom_simplified is 'Geometría simplificada (~200 m) para el mapa; usar geom para cálculos.';

-- ─────────────────────────────────────────────────────────────────────
-- 2. RESOLUCIÓN TEMPORAL
-- ─────────────────────────────────────────────────────────────────────
alter table public.variables
  add column temporal_res text not null default 'monthly'
    check (temporal_res in ('daily','monthly','static','derived'));

update public.variables set temporal_res = 'derived'
 where id in ('water_balance','ndvi_anom','temp_change_c','precip_change_pct','et0');

comment on column public.variables.temporal_res is
  'Resolución con la que se GUARDA la serie. Los umbrales de enfermedad se evalúan sobre valores diarios (ver disease_thresholds.resolution).';

alter table public.disease_thresholds
  add column resolution text not null default 'daily' check (resolution in ('daily','monthly'));

comment on column public.disease_thresholds.resolution is
  'Granularidad sobre la que el ETL evalúa la regla. daily = valor diario de la variable (ERA5-Land/GPM diarios).';

-- ─────────────────────────────────────────────────────────────────────
-- 3. PELIGROS CLIMÁTICOS POR ÁREA Y MES
-- ─────────────────────────────────────────────────────────────────────
create table public.area_monthly_hazard (
  area_id                  uuid not null references public.areas(id) on delete cascade,
  month_date               date not null,            -- día 1 del mes
  precip_total_mm          numeric,                  -- GPM
  wet_days                 smallint,                 -- lluvia ≥ 1 mm
  heavy_rain_days          smallint,                 -- lluvia ≥ 50 mm
  max_consecutive_wet_days smallint,
  rh_mean                  numeric,                  -- ERA5-Land
  humid_days               smallint,                 -- HR media ≥ 80 %
  t2m_mean                 numeric,
  hot_days                 smallint,                 -- T media > 32 °C (sobre el óptimo)
  saturated_days           smallint,                 -- SMAP / ERA5 capa 1 sobre umbral
  n_days_with_data         smallint,                 -- control de calidad
  computed_at              timestamptz default now(),
  primary key (area_id, month_date)
);
comment on table public.area_monthly_hazard is
  'Conteos climáticos mensuales por área, independientes del patógeno. Insumo del índice de riesgo y del modelo.';

-- disease_risk_monthly deja de repetir los peligros
drop view public.v_training_area_year;

alter table public.disease_risk_monthly
  drop column wet_days,
  drop column heavy_rain_days,
  drop column saturated_days,
  add column max_consecutive_favorable_days smallint,
  add column n_days_with_data smallint;

-- ─────────────────────────────────────────────────────────────────────
-- 4. FENOLOGÍA DEL CULTIVO
-- ─────────────────────────────────────────────────────────────────────
create table public.crop_phenology (
  crop_id         text not null references public.crops(id) on delete cascade,
  region          text not null check (region in ('costa','sierra','amazonia','insular')),
  stage           text not null,            -- 'floracion', 'desarrollo_mazorca', 'cosecha_principal', ...
  months          smallint[] not null,      -- meses del año (1–12)
  is_risk_window  boolean not null default false,  -- ¿cuenta para el riesgo de enfermedad?
  source_ref      text,
  validated       boolean not null default false,
  notes           text,
  primary key (crop_id, region, stage)
);
comment on table public.crop_phenology is
  'Calendario del cultivo por región. La ventana de riesgo define qué meses suma el índice de enfermedad y el modelo.';

insert into public.crop_phenology (crop_id, region, stage, months, is_risk_window, source_ref, notes) values
 ('cacao', 'costa',    'floracion',          '{12,1,2}',           false, 'referencial — por validar', 'Inicia con las primeras lluvias.'),
 ('cacao', 'costa',    'desarrollo_mazorca', '{1,2,3,4,5,6}',      true,  'referencial — por validar', 'Mazorcas jóvenes en época lluviosa: ventana de infección de moniliasis y mazorca negra.'),
 ('cacao', 'costa',    'cosecha_principal',  '{3,4,5,6,7}',        false, 'referencial — por validar', null),
 ('cacao', 'costa',    'cosecha_secundaria', '{10,11,12}',         false, 'referencial — por validar', null),
 ('cacao', 'amazonia', 'desarrollo_mazorca', '{1,2,3,4,5,6,7,8,9,10,11,12}', true, 'referencial — por validar', 'Lluvia todo el año: ventana continua.');

-- ─────────────────────────────────────────────────────────────────────
-- 5. CLASIFICACIÓN ANUAL DE ENSO (regla única y versionada)
-- ─────────────────────────────────────────────────────────────────────
create view public.v_enso_year_class with (security_invoker = true) as
with m as (
  select extract(year from month_date)::smallint as year,
         avg(value) filter (where index_id = 'oni')         as oni_jan_jun,
         max(value) filter (where index_id = 'oni')         as oni_max_jan_jun,
         avg(value) filter (where index_id = 'nino12_anom') as nino12_anom_jan_jun,
         max(value) filter (where index_id = 'nino12_anom') as nino12_max_jan_jun
    from public.enso_index
   where extract(month from month_date) between 1 and 6
   group by 1
)
select year, oni_jan_jun, oni_max_jan_jun, nino12_anom_jan_jun, nino12_max_jan_jun,
       case
         when oni_jan_jun >= 0.5 or nino12_anom_jan_jun >= 0.4 then 'nino'
         when oni_jan_jun <= -0.5                               then 'nina'
         else 'neutral'
       end as enso_class,
       (nino12_anom_jan_jun >= 0.4 and coalesce(oni_jan_jun, 0) < 0.5) as is_coastal_nino
  from m;
comment on view public.v_enso_year_class is
  'Regla única para los escenarios normal/nino/nina: promedio enero–junio. Niño si ONI ≥ 0.5 o Niño 1+2 ≥ 0.4 (Niño costero); Niña si ONI ≤ −0.5.';

-- ─────────────────────────────────────────────────────────────────────
-- 6. EFECTO DE CADA ESTRATEGIA POR OBJETIVO
-- ─────────────────────────────────────────────────────────────────────
create table public.strategy_effects (
  strategy_id         text not null references public.adaptation_strategies(id) on delete cascade,
  target              text not null,       -- 'monilia','phytophthora','escoba_bruja','encharcamiento','calor','ingreso'
  reduction_pct_low   numeric check (reduction_pct_low  between 0 and 100),
  reduction_pct_high  numeric check (reduction_pct_high between 0 and 100),
  source_ref          text,
  validated           boolean not null default false,
  notes               text,
  primary key (strategy_id, target)
);
comment on table public.strategy_effects is
  'Cuánto reduce cada estrategia cada problema. Permite ordenar estrategias según el patógeno que domina en el cantón.';

insert into public.strategy_effects (strategy_id, target, notes) values
 ('sanitario',       'monilia',        'Completar con literatura / INIAP'),
 ('sanitario',       'phytophthora',   'Completar con literatura / INIAP'),
 ('sanitario',       'escoba_bruja',   'Completar con literatura / INIAP'),
 ('drenaje_sombra',  'phytophthora',   'Completar con literatura / INIAP'),
 ('drenaje_sombra',  'encharcamiento', 'Completar con literatura / INIAP'),
 ('drenaje_sombra',  'calor',          'Completar con literatura / INIAP'),
 ('diversificacion', 'ingreso',        'Completar con literatura / INIAP');

-- Una sola fuente de verdad: se quitan los campos resumidos de la estrategia.
alter table public.adaptation_strategies
  drop column targets,
  drop column loss_reduction_pct_low,
  drop column loss_reduction_pct_high;

-- ─────────────────────────────────────────────────────────────────────
-- 7. VISTA PARA EL MAPA
-- ─────────────────────────────────────────────────────────────────────
create view public.v_loss_map with (security_invoker = true) as
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
       mv.name         as model_name
  from public.loss_predictions lp
  join public.model_versions mv on mv.id = lp.model_version_id and mv.is_active
  join public.areas a           on a.id  = lp.area_id
  left join public.areas p      on p.id  = a.parent_id;
comment on view public.v_loss_map is 'Una fila por área × escenario con todo lo que necesita el mapa (solo el modelo activo).';

-- ─────────────────────────────────────────────────────────────────────
-- 8. REGISTRO DE CARGAS
-- ─────────────────────────────────────────────────────────────────────
create table public.etl_runs (
  id            bigint generated always as identity primary key,
  script        text not null,              -- 'etl_enso', 'etl_climate', ...
  params        jsonb,                      -- {"provinces": [...], "years": "2001-2025"}
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  status        text not null default 'running' check (status in ('running','done','error')),
  rows_written  integer,
  error         text,
  notes         text
);
create index etl_runs_script_idx on public.etl_runs (script, started_at desc);

-- ─────────────────────────────────────────────────────────────────────
-- 9. FUENTE DE VERDAD DEL CULTIVO
-- ─────────────────────────────────────────────────────────────────────
comment on table  public.crop_requirements is 'Fuente de verdad de los requerimientos del cultivo (ECOCROP).';
comment on column public.crops.temp_opt_min_c    is 'Heredado de v1; usar crop_requirements.';
comment on column public.crops.temp_opt_max_c    is 'Heredado de v1; usar crop_requirements.';
comment on column public.crops.rain_min_mm_cycle is 'Heredado de v1; usar crop_requirements.';
comment on column public.crops.rain_max_mm_cycle is 'Heredado de v1; usar crop_requirements.';

-- ─────────────────────────────────────────────────────────────────────
-- VISTA DE ENTRENAMIENTO (recreada: usa fenología, peligros y ENSO anual)
-- ─────────────────────────────────────────────────────────────────────
create view public.v_training_area_year with (security_invoker = true) as
with win as (
  select crop_id, region, unnest(months) as month
    from public.crop_phenology
   where is_risk_window
),
risk as (
  select d.area_id, pg.crop_id, extract(year from d.month_date)::smallint as year,
         sum(d.favorable_days) filter (where d.pathogen_id = 'monilia')      as fav_days_monilia,
         sum(d.favorable_days) filter (where d.pathogen_id = 'phytophthora') as fav_days_phytophthora,
         sum(d.favorable_days) filter (where d.pathogen_id = 'escoba_bruja') as fav_days_escoba,
         avg(d.risk_index)                                                  as risk_index_mean,
         max(d.max_consecutive_favorable_days)                              as max_consec_favorable
    from public.disease_risk_monthly d
    join public.pathogens pg on pg.id = d.pathogen_id
    join public.areas a      on a.id  = d.area_id
    join win w on w.crop_id = pg.crop_id
             and w.region  = coalesce(a.region, 'costa')
             and w.month   = extract(month from d.month_date)
   group by 1, 2, 3
),
hazard as (
  select h.area_id, w.crop_id, extract(year from h.month_date)::smallint as year,
         sum(h.precip_total_mm)          as precip_total_mm,
         sum(h.wet_days)                 as wet_days,
         sum(h.heavy_rain_days)          as heavy_rain_days,
         max(h.max_consecutive_wet_days) as max_consecutive_wet_days,
         avg(h.rh_mean)                  as rh_mean,
         sum(h.humid_days)               as humid_days,
         avg(h.t2m_mean)                 as t2m_mean,
         sum(h.hot_days)                 as hot_days,
         sum(h.saturated_days)           as saturated_days
    from public.area_monthly_hazard h
    join public.areas a on a.id = h.area_id
    join win w on w.region = coalesce(a.region, 'costa')
             and w.month  = extract(month from h.month_date)
   group by 1, 2, 3
)
select s.area_id, s.crop_id, s.year,
       s.yield_t_ha, s.harvested_ha, s.lost_ha, s.production_t,
       r.fav_days_monilia, r.fav_days_phytophthora, r.fav_days_escoba,
       r.risk_index_mean, r.max_consec_favorable,
       h.precip_total_mm, h.wet_days, h.heavy_rain_days, h.max_consecutive_wet_days,
       h.rh_mean, h.humid_days, h.t2m_mean, h.hot_days, h.saturated_days,
       e.oni_jan_jun, e.nino12_anom_jan_jun, e.enso_class, e.is_coastal_nino,
       cs.score as suitability_now
  from public.crop_production_stats s
  join risk   r on r.area_id = s.area_id and r.crop_id = s.crop_id and r.year = s.year
  left join hazard h on h.area_id = s.area_id and h.crop_id = s.crop_id and h.year = s.year
  left join public.v_enso_year_class e on e.year = s.year
  left join public.crop_suitability cs
         on cs.area_id = s.area_id and cs.crop_id = s.crop_id and cs.scenario_id = 'normal';
comment on view public.v_training_area_year is
  'Dataset área × año para el modelo: rendimiento real + riesgo y peligros en la ventana de riesgo + ENSO + aptitud.';

-- ─────────────────────────────────────────────────────────────────────
-- SEGURIDAD
-- ─────────────────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array['area_monthly_hazard','crop_phenology','strategy_effects','etl_runs'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "public read" on public.%I for select using (true)', t);
  end loop;
end $$;
