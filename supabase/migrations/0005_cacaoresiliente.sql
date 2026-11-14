-- =====================================================================
--  CacaoResiliente — esquema del proyecto (se aplica sobre 0001–0004)
-- =====================================================================
--  Reutiliza: data_sources, variables, crops, areas, area_monthly_series.
--  Bloques nuevos:
--    A. Cultivo y requerimientos (ECOCROP)
--    B. Patógenos y umbrales de enfermedad
--    C. El Niño (ENSO) y escenarios
--    D. Clima por escenario
--    E. Exposición: producción, superficie, precios
--    F. Índices calculados: riesgo de enfermedad y aptitud
--    G. Modelo predictivo y predicciones de pérdida
--    H. Estrategias de adaptación
--    I. Validación en campo
-- =====================================================================

-- ─────────────────────────────────────────────────────────────────────
-- A. CULTIVO Y REQUERIMIENTOS
-- ─────────────────────────────────────────────────────────────────────

-- Requerimientos en formato largo: un parámetro por fila, numérico o categórico.
create table public.crop_requirements (
  crop_id      text not null references public.crops(id) on delete cascade,
  parameter    text not null,              -- 'temp_mean', 'rain_annual', 'ph', 'altitude', ...
  opt_min      numeric,
  opt_max      numeric,
  abs_min      numeric,
  abs_max      numeric,
  value_text   text,                       -- para categóricos: luz, textura, drenaje
  unit         text,
  source_ref   text not null default 'ECOCROP (OpenCLIM/ecocrop, EcoCrop_DB.csv)',
  notes        text,
  primary key (crop_id, parameter)
);

-- ─────────────────────────────────────────────────────────────────────
-- B. PATÓGENOS Y UMBRALES
-- ─────────────────────────────────────────────────────────────────────

create table public.pathogens (
  id               text primary key,       -- 'monilia', 'phytophthora', 'escoba_bruja'
  name_es          text not null,
  scientific_name  text not null,
  crop_id          text not null references public.crops(id),
  organ_affected   text,                   -- 'mazorca', 'brotes', ...
  spread_by        text[],                 -- {'viento','lluvia','salpique'}
  description      text
);

-- Condiciones que vuelven "favorable" un día para el patógeno.
-- Un día es favorable si cumple TODAS las reglas del patógeno.
create table public.disease_thresholds (
  id             bigint generated always as identity primary key,
  pathogen_id    text not null references public.pathogens(id) on delete cascade,
  variable_id    text not null references public.variables(id),
  min_value      numeric,                  -- null = sin límite inferior
  max_value      numeric,                  -- null = sin límite superior
  unit           text not null,
  min_consecutive_days smallint default 1,
  weight         numeric not null default 1,
  validated      boolean not null default false,   -- true cuando lo confirme un experto
  source_ref     text,
  notes          text
);

-- ─────────────────────────────────────────────────────────────────────
-- C. EL NIÑO (ENSO) Y ESCENARIOS
-- ─────────────────────────────────────────────────────────────────────

-- Series mensuales de NOAA CPC: ONI y anomalías de temperatura del mar.
create table public.enso_index (
  index_id     text not null check (index_id in ('oni','nino12_anom','nino3_anom','nino34_anom','nino4_anom')),
  month_date   date not null,              -- día 1 del mes (ONI: mes central del trimestre)
  value        numeric not null,
  phase        text generated always as (
                 case
                   when index_id = 'oni'         and value >=  0.5 then 'nino'
                   when index_id = 'oni'         and value <= -0.5 then 'nina'
                   when index_id = 'nino12_anom' and value >=  0.4 then 'nino'
                   when index_id = 'nino12_anom' and value <= -0.4 then 'nina'
                   when index_id in ('oni','nino12_anom') then 'neutral'
                 end) stored,
  fetched_at   timestamptz default now(),
  primary key (index_id, month_date)
);

-- Eventos identificados por el ETL (≥ 5 trimestres ONI ≥ 0.5 o Niño costero).
create table public.enso_events (
  id            text primary key,          -- 'nino_1997_98', 'nino_costero_2017'...
  phase         text not null check (phase in ('nino','nina')),
  start_month   date not null,
  end_month     date,                      -- null = en curso
  peak_oni      numeric,
  peak_nino12   numeric,
  intensity     text check (intensity in ('debil','moderado','fuerte','muy_fuerte')),
  is_coastal    boolean default false,     -- Niño costero (Niño 1+2 alto, ONI bajo)
  notes         text
);

create table public.scenarios (
  id            text primary key,
  name_es       text not null,
  kind          text not null check (kind in ('historical','current','projection')),
  phase         smallint not null,         -- fase del proyecto en que se usa
  period_start  smallint,
  period_end    smallint,
  ssp           text,                      -- 'ssp245', 'ssp585'
  description   text
);

-- ─────────────────────────────────────────────────────────────────────
-- D. CLIMA POR ESCENARIO
-- ─────────────────────────────────────────────────────────────────────

-- Climatología mensual de cada escenario (la serie observada vive en area_monthly_series).
create table public.area_scenario_climate (
  area_id       uuid not null references public.areas(id) on delete cascade,
  scenario_id   text not null references public.scenarios(id),
  variable_id   text not null references public.variables(id),
  month         smallint not null check (month between 1 and 12),
  value_mean    numeric not null,
  value_min     numeric,                   -- mínimo entre años o modelos
  value_max     numeric,
  n_members     smallint,                  -- nº de años (históricos) o modelos (CMIP6)
  method        text not null check (method in ('composite','delta','raw_model')),
  computed_at   timestamptz default now(),
  primary key (area_id, scenario_id, variable_id, month)
);

-- ─────────────────────────────────────────────────────────────────────
-- E. EXPOSICIÓN: PRODUCCIÓN, SUPERFICIE, PRECIOS
-- ─────────────────────────────────────────────────────────────────────

-- Estadísticas oficiales (ESPAC por provincia, FAOSTAT nacional).
create table public.crop_production_stats (
  id              bigint generated always as identity primary key,
  area_id         uuid not null references public.areas(id) on delete cascade,
  crop_id         text not null references public.crops(id),
  year            smallint not null,
  planted_ha      numeric,
  productive_ha   numeric,                 -- en edad productiva
  harvested_ha    numeric,
  lost_ha         numeric,
  production_t    numeric,
  yield_t_ha      numeric generated always as (production_t / nullif(harvested_ha, 0)) stored,
  source_id       text not null references public.data_sources(id),
  notes           text,
  unique (area_id, crop_id, year, source_id)
);

-- Superficie de cacao por cantón (para repartir la producción provincial).
create table public.crop_exposure (
  area_id       uuid not null references public.areas(id) on delete cascade,
  crop_id       text not null references public.crops(id),
  ref_year      smallint not null,
  crop_ha       numeric not null,
  method        text not null check (method in ('espac_direct','downscaled_landcover','manual')),
  source_id     text references public.data_sources(id),
  primary key (area_id, crop_id, ref_year)
);

create table public.crop_prices (
  crop_id       text not null references public.crops(id),
  month_date    date not null,
  market        text not null default 'nacional',
  product_form  text not null default 'grano_seco',
  price_usd_t   numeric not null,
  source_id     text not null references public.data_sources(id),
  primary key (crop_id, month_date, market, product_form)
);

-- ─────────────────────────────────────────────────────────────────────
-- F. ÍNDICES CALCULADOS
-- ─────────────────────────────────────────────────────────────────────

-- Historia observada (alimenta el entrenamiento del modelo).
create table public.disease_risk_monthly (
  area_id          uuid not null references public.areas(id) on delete cascade,
  pathogen_id      text not null references public.pathogens(id),
  month_date       date not null,
  favorable_days   smallint not null,      -- días que cumplen los umbrales
  wet_days         smallint,               -- días con lluvia ≥ 1 mm
  heavy_rain_days  smallint,               -- días con lluvia ≥ 50 mm
  saturated_days   smallint,               -- días con suelo saturado (SMAP)
  risk_index       numeric not null check (risk_index between 0 and 1),
  details          jsonb,
  computed_at      timestamptz default now(),
  primary key (area_id, pathogen_id, month_date)
);

-- Riesgo climatológico por escenario (normal, Niño, 2050).
create table public.disease_risk_scenario (
  area_id          uuid not null references public.areas(id) on delete cascade,
  pathogen_id      text not null references public.pathogens(id),
  scenario_id      text not null references public.scenarios(id),
  month            smallint not null check (month between 1 and 12),
  risk_mean        numeric not null check (risk_mean between 0 and 1),
  risk_min         numeric,
  risk_max         numeric,
  favorable_days   numeric,
  computed_at      timestamptz default now(),
  primary key (area_id, pathogen_id, scenario_id, month)
);

create table public.crop_suitability (
  area_id           uuid not null references public.areas(id) on delete cascade,
  crop_id           text not null references public.crops(id),
  scenario_id       text not null references public.scenarios(id),
  score             numeric not null check (score between 0 and 1),
  class             text not null check (class in ('optima','apta','marginal','no_apta')),
  limiting_factors  text[],                -- {'temp_mean','rain_annual'}
  details           jsonb,                 -- puntaje por parámetro
  computed_at       timestamptz default now(),
  primary key (area_id, crop_id, scenario_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- G. MODELO PREDICTIVO
-- ─────────────────────────────────────────────────────────────────────

create table public.model_versions (
  id                 uuid primary key default gen_random_uuid(),
  name               text not null,        -- 'cacao_loss_v1'
  crop_id            text not null references public.crops(id),
  target             text not null,        -- 'yield_anomaly_pct'
  algorithm          text not null,        -- 'ridge', 'gbr_quantile', ...
  features           text[] not null,
  hyperparams        jsonb,
  cv_scheme          text,                 -- 'leave_one_year_out'
  metrics            jsonb,                -- {"mae":..,"r2":..,"skill_vs_baseline":..}
  train_start_year   smallint,
  train_end_year     smallint,
  n_samples          integer,
  artifact_path      text,                 -- ruta en Supabase Storage del .joblib
  is_active          boolean not null default false,
  created_at         timestamptz default now()
);
create unique index model_versions_one_active on public.model_versions (crop_id) where is_active;

-- Copia exacta del dataset usado (reproducibilidad).
create table public.training_samples (
  model_version_id  uuid not null references public.model_versions(id) on delete cascade,
  area_id           uuid not null references public.areas(id) on delete cascade,
  year              smallint not null,
  features          jsonb not null,
  target            numeric not null,
  fold              smallint,
  prediction_cv     numeric,               -- predicción fuera de muestra
  primary key (model_version_id, area_id, year)
);

create table public.loss_predictions (
  id                uuid primary key default gen_random_uuid(),
  model_version_id  uuid not null references public.model_versions(id) on delete cascade,
  area_id           uuid not null references public.areas(id) on delete cascade,
  crop_id           text not null references public.crops(id),
  scenario_id       text not null references public.scenarios(id),
  loss_pct          numeric not null,      -- pérdida esperada de rendimiento (%)
  loss_pct_low      numeric,               -- percentil 10
  loss_pct_high     numeric,               -- percentil 90
  exposed_ha        numeric,
  expected_yield_t_ha numeric,
  loss_t            numeric,
  price_usd_t       numeric,
  loss_usd          numeric,
  risk_class        text check (risk_class in ('bajo','medio','alto','muy_alto')),
  top_factors       jsonb,                 -- [{"feature":"favorable_days_monilia","contribution":4.1}]
  created_at        timestamptz default now(),
  unique (model_version_id, area_id, crop_id, scenario_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- H. ESTRATEGIAS DE ADAPTACIÓN
-- ─────────────────────────────────────────────────────────────────────

create table public.adaptation_strategies (
  id                       text primary key,
  name_es                  text not null,
  description              text not null,
  targets                  text[] not null,   -- {'monilia','phytophthora','encharcamiento','ingreso'}
  loss_reduction_pct_low   numeric,           -- completar con literatura / INIAP
  loss_reduction_pct_high  numeric,
  cost_usd_ha_year         numeric,
  applies_to_zones         text[],            -- {'manejo','critica'}
  evidence                 text,
  source_ref               text,
  validated                boolean not null default false
);

create table public.strategy_evaluations (
  id                  uuid primary key default gen_random_uuid(),
  prediction_id       uuid not null references public.loss_predictions(id) on delete cascade,
  strategy_id         text not null references public.adaptation_strategies(id),
  rank                smallint not null,
  expected_loss_pct   numeric,
  avoided_loss_usd    numeric,
  net_benefit_usd     numeric,               -- pérdida evitada − costo
  why                 text,
  evidence            jsonb,                 -- [{variable_id, source_id, statement}]
  data_gaps           text[],
  risks               text[],
  unique (prediction_id, strategy_id)
);

-- Fase 2: matriz aptitud futura × riesgo Niño.
create table public.zone_classification (
  area_id             uuid not null references public.areas(id) on delete cascade,
  crop_id             text not null references public.crops(id),
  future_scenario_id  text not null references public.scenarios(id),
  zone_class          text not null check (zone_class in ('segura','manejo','transicion','critica')),
  suitability_now     numeric,
  suitability_future  numeric,
  nino_risk           numeric,
  computed_at         timestamptz default now(),
  primary key (area_id, crop_id, future_scenario_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- I. VALIDACIÓN EN CAMPO
-- ─────────────────────────────────────────────────────────────────────

create table public.field_observations (
  id              bigint generated always as identity primary key,
  area_id         uuid references public.areas(id) on delete set null,
  pathogen_id     text references public.pathogens(id),
  observed_on     date not null,
  lat             numeric,
  lon             numeric,
  pods_total      integer,
  pods_diseased   integer,
  incidence_pct   numeric generated always as (100.0 * pods_diseased / nullif(pods_total, 0)) stored,
  severity        smallint check (severity between 0 and 5),
  source          text not null check (source in ('gbif','tecnico','agricultor')),
  external_id     text,                      -- id de GBIF
  observer_id     uuid references auth.users(id) on delete set null,
  notes           text,
  created_at      timestamptz default now(),
  unique (source, external_id)
);

create table public.strategy_reviews (
  id                bigint generated always as identity primary key,
  evaluation_id     uuid not null references public.strategy_evaluations(id) on delete cascade,
  reviewer_id       uuid references auth.users(id) on delete set null,
  reviewer_role     text check (reviewer_role in ('agricultor','agronomo','fitopatologo','otro')),
  verdict           text check (verdict in ('de_acuerdo','parcial','en_desacuerdo')),
  comment           text,
  created_at        timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────────────
-- ÍNDICES DE CLAVES FORÁNEAS
-- ─────────────────────────────────────────────────────────────────────
create index on public.disease_thresholds (pathogen_id);
create index on public.disease_thresholds (variable_id);
create index on public.pathogens (crop_id);
create index on public.area_scenario_climate (scenario_id);
create index on public.area_scenario_climate (variable_id);
create index on public.crop_production_stats (crop_id);
create index on public.crop_production_stats (source_id);
create index on public.crop_exposure (crop_id);
create index on public.crop_exposure (source_id);
create index on public.crop_prices (source_id);
create index on public.disease_risk_monthly (pathogen_id);
create index on public.disease_risk_scenario (pathogen_id);
create index on public.disease_risk_scenario (scenario_id);
create index on public.crop_suitability (crop_id);
create index on public.crop_suitability (scenario_id);
create index on public.training_samples (area_id);
create index on public.loss_predictions (area_id);
create index on public.loss_predictions (crop_id);
create index on public.loss_predictions (scenario_id);
create index on public.strategy_evaluations (strategy_id);
create index on public.zone_classification (crop_id);
create index on public.zone_classification (future_scenario_id);
create index on public.field_observations (area_id);
create index on public.field_observations (pathogen_id);
create index on public.field_observations (observer_id);
create index on public.strategy_reviews (evaluation_id);
create index on public.strategy_reviews (reviewer_id);

-- ─────────────────────────────────────────────────────────────────────
-- VISTA: dataset de entrenamiento (área × año)
--   Temporada de riesgo = enero–junio (época lluviosa en la Costa).
-- ─────────────────────────────────────────────────────────────────────
create view public.v_training_area_year with (security_invoker = true) as
with risk as (
  select area_id, extract(year from month_date)::smallint as year,
         sum(favorable_days) filter (where pathogen_id = 'monilia')      as fav_days_monilia,
         sum(favorable_days) filter (where pathogen_id = 'phytophthora') as fav_days_phytophthora,
         sum(heavy_rain_days) filter (where pathogen_id = 'monilia')     as heavy_rain_days,
         sum(saturated_days)  filter (where pathogen_id = 'monilia')     as saturated_days,
         avg(risk_index)                                                  as risk_index_mean
    from public.disease_risk_monthly
   where extract(month from month_date) between 1 and 6
   group by 1, 2
),
enso as (
  select extract(year from month_date)::smallint as year,
         avg(value) filter (where index_id = 'nino12_anom') as nino12_anom_jan_jun,
         avg(value) filter (where index_id = 'oni')         as oni_jan_jun
    from public.enso_index
   where extract(month from month_date) between 1 and 6
   group by 1
)
select s.area_id, s.crop_id, s.year, s.yield_t_ha, s.harvested_ha, s.lost_ha,
       r.fav_days_monilia, r.fav_days_phytophthora, r.heavy_rain_days,
       r.saturated_days, r.risk_index_mean,
       e.nino12_anom_jan_jun, e.oni_jan_jun,
       cs.score as suitability_now
  from public.crop_production_stats s
  join risk r  on r.area_id = s.area_id and r.year = s.year
  left join enso e on e.year = s.year
  left join public.crop_suitability cs
         on cs.area_id = s.area_id and cs.crop_id = s.crop_id and cs.scenario_id = 'normal';

-- ─────────────────────────────────────────────────────────────────────
-- SEGURIDAD (RLS): todo es lectura pública; escribe solo el backend
-- (service_role). Observaciones y revisiones: cada usuario las suyas.
-- ─────────────────────────────────────────────────────────────────────
do $$
declare t text;
begin
  foreach t in array array[
    'crop_requirements','pathogens','disease_thresholds','enso_index','enso_events',
    'scenarios','area_scenario_climate','crop_production_stats','crop_exposure',
    'crop_prices','disease_risk_monthly','disease_risk_scenario','crop_suitability',
    'model_versions','training_samples','loss_predictions','adaptation_strategies',
    'strategy_evaluations','zone_classification','field_observations','strategy_reviews']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "public read" on public.%I for select using (true)', t);
  end loop;
end $$;

create policy "own insert" on public.field_observations for insert to authenticated
  with check (observer_id = (select auth.uid()) and source in ('tecnico','agricultor'));
create policy "own update" on public.field_observations for update to authenticated
  using (observer_id = (select auth.uid())) with check (observer_id = (select auth.uid()));
create policy "own insert" on public.strategy_reviews for insert to authenticated
  with check (reviewer_id = (select auth.uid()));
create policy "own update" on public.strategy_reviews for update to authenticated
  using (reviewer_id = (select auth.uid())) with check (reviewer_id = (select auth.uid()));

-- ─────────────────────────────────────────────────────────────────────
-- SEMILLAS
-- ─────────────────────────────────────────────────────────────────────

insert into public.data_sources (id, name, provider, access, dataset_ref, temporal_res, url, citation) values
 ('noaa_cpc', 'NOAA CPC ENSO indices (ONI, Niño 1+2)', 'NOAA',  'other', 'oni.ascii.txt / sstoi.indices', 'monthly', 'https://www.cpc.ncep.noaa.gov/data/indices/', null),
 ('espac',    'ESPAC — Encuesta de Superficie y Producción Agropecuaria Continua', 'INEC', 'other', 'descarga CSV/XLSX', 'annual', 'https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/', null),
 ('faostat',  'FAOSTAT Production (QCL)', 'FAO', 'other', 'Production_Crops_Livestock_E_Americas.zip', 'annual', 'https://www.fao.org/faostat/', null),
 ('sipa',     'SIPA — precios agropecuarios', 'MAG Ecuador', 'other', 'descarga manual', 'monthly', 'http://sipa.agricultura.gob.ec/', null),
 ('gbif',     'GBIF occurrences', 'GBIF', 'other', 'api.gbif.org/v1/occurrence/search', 'irregular', 'https://www.gbif.org', null),
 ('ecocrop',  'ECOCROP (OpenCLIM)', 'FAO / OpenCLIM', 'other', 'EcoCrop_DB.csv', 'static', 'https://github.com/OpenCLIM/ecocrop', null)
on conflict (id) do nothing;

insert into public.variables (id, name, unit, source_id, description) values
 ('rh_mean',        'Humedad relativa media diaria',         '%',        'era5_land', 'Calculada con temperatura y punto de rocío de ERA5-Land.'),
 ('wet_days',       'Días con lluvia (≥ 1 mm)',              'días/mes', 'gpm_imerg', 'Días en que llovió; las esporas se dispersan con la lluvia.'),
 ('saturated_days', 'Días con suelo saturado',               'días/mes', 'smap_l4',   'Días con humedad superficial muy alta: riesgo de asfixia de raíces.'),
 ('hot_days',       'Días sobre el óptimo (> 32 °C)',        'días/mes', 'era5_land', 'Días más calientes que el óptimo del cacao.'),
 ('ndvi_anom',      'Anomalía de NDVI',                      'índice',   'modis_ndvi','Diferencia del verdor frente al promedio del mismo mes.')
on conflict (id) do nothing;

insert into public.crops (id, name_es, scientific_name, family, crop_type, region, cycle_days, is_perennial,
                          temp_opt_min_c, temp_opt_max_c, temp_abs_min_c, temp_abs_max_c,
                          rain_min_mm_cycle, rain_max_mm_cycle, altitude_max_m, ph_min, ph_max, source_ref)
values ('cacao', 'Cacao', 'Theobroma cacao', 'Malvaceae', 'perennial', '{costa,amazonia}', null, true,
        21, 32, 10, 38, 1200, 3000, 900, 5.0, 6.5, 'ECOCROP (OpenCLIM/ecocrop)')
on conflict (id) do nothing;

insert into public.crop_requirements (crop_id, parameter, opt_min, opt_max, abs_min, abs_max, value_text, unit) values
 ('cacao', 'temp_mean',    21,   32,   10,   38,   null,                         '°C'),
 ('cacao', 'rain_annual',  1200, 3000, 900,  7600, null,                         'mm/año'),
 ('cacao', 'ph',           5.0,  6.5,  null, null, null,                         'pH'),
 ('cacao', 'altitude',     null, 900,  null, null, null,                         'm'),
 ('cacao', 'killing_temp', null, null, 0,    null, null,                         '°C'),
 ('cacao', 'growth_days',  180,  365,  null, null, null,                         'días'),
 ('cacao', 'light',        null, null, null, null, 'cielo despejado a sombra ligera', null),
 ('cacao', 'soil_depth',   null, null, null, null, 'profundo (>150 cm)',         null),
 ('cacao', 'soil_texture', null, null, null, null, 'pesado, orgánico',           null),
 ('cacao', 'drainage',     null, null, null, null, 'bien drenado (tolera periodos secos)', null)
on conflict do nothing;

insert into public.pathogens (id, name_es, scientific_name, crop_id, organ_affected, spread_by, description) values
 ('monilia',      'Moniliasis',     'Moniliophthora roreri',     'cacao', 'mazorca', '{viento,lluvia}',   'Pudrición helada de la mazorca; favorecida por humedad alta sostenida.'),
 ('phytophthora', 'Mazorca negra',  'Phytophthora spp.',         'cacao', 'mazorca', '{lluvia,salpique}', 'Pudrición negra; favorecida por lluvia y mazorcas mojadas.'),
 ('escoba_bruja', 'Escoba de bruja','Moniliophthora perniciosa', 'cacao', 'brotes',  '{viento,lluvia}',   'Deforma brotes y cojines florales; favorecida por humedad.')
on conflict (id) do nothing;

-- Umbrales REFERENCIALES (validated = false): confirmar con INIAP / fitopatólogo.
insert into public.disease_thresholds (pathogen_id, variable_id, min_value, max_value, unit, weight, source_ref, notes) values
 ('monilia',      'rh_mean', 80,   null, '%',  1, 'literatura — por validar', 'HR media diaria alta'),
 ('monilia',      't2m',     20,   28,   '°C', 1, 'literatura — por validar', 'Rango térmico favorable'),
 ('phytophthora', 'precip',  1,    null, 'mm/día', 1, 'literatura — por validar', 'Día con lluvia (salpique)'),
 ('phytophthora', 'rh_mean', 85,   null, '%',  1, 'literatura — por validar', 'Ambiente casi saturado'),
 ('phytophthora', 't2m',     20,   30,   '°C', 1, 'literatura — por validar', null),
 ('escoba_bruja', 'rh_mean', 80,   null, '%',  1, 'literatura — por validar', null),
 ('escoba_bruja', 't2m',     20,   30,   '°C', 1, 'literatura — por validar', null);

insert into public.scenarios (id, name_es, kind, phase, period_start, period_end, ssp, description) values
 ('normal',      'Año normal (neutro)',   'historical', 1, 2001, 2025, null,     'Promedio de años ENSO neutros.'),
 ('nino',        'Año Niño',              'historical', 1, 2001, 2025, null,     'Promedio de años con El Niño (ONI ≥ 0.5 o Niño costero).'),
 ('nina',        'Año Niña',              'historical', 1, 2001, 2025, null,     'Promedio de años con La Niña.'),
 ('actual',      'Temporada en curso',    'current',    1, 2026, 2027, null,     'Condiciones ENSO actuales según NOAA CPC.'),
 ('ssp245_2050', '2050 — emisiones moderadas', 'projection', 2, 2041, 2060, 'ssp245', 'NEX-GDDP-CMIP6, 4 modelos, método delta.'),
 ('ssp585_2050', '2050 — emisiones altas',     'projection', 2, 2041, 2060, 'ssp585', 'NEX-GDDP-CMIP6, 4 modelos, método delta.')
on conflict (id) do nothing;

insert into public.adaptation_strategies (id, name_es, description, targets, applies_to_zones, evidence) values
 ('actual',          'Manejo actual',                 'Línea base: sin cambios en el manejo.', '{}', '{segura,manejo,transicion,critica}', null),
 ('sanitario',       'Manejo sanitario',              'Cosecha sanitaria semanal, poda y retiro de mazorcas enfermas.', '{monilia,phytophthora,escoba_bruja}', '{manejo,critica}', 'Completar con literatura / INIAP'),
 ('drenaje_sombra',  'Drenaje + sombra regulada',     'Canales de drenaje y ajuste de sombra en sistema agroforestal.', '{phytophthora,encharcamiento,calor}', '{manejo,transicion}', 'Completar con literatura / INIAP'),
 ('diversificacion', 'Diversificación',               'Cacao con plátano y maderables; rotación de cultivos intercalados en cacao joven.', '{ingreso}', '{transicion,critica}', 'Completar con literatura / INIAP')
on conflict (id) do nothing;
