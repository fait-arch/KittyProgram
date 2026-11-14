-- =====================================================================
--  AgroRotación UIDE — esquema inicial (Supabase / Postgres + PostGIS)
-- =====================================================================
--  4 bloques:
--    A. Referencia   → catálogo de fuentes NASA y de cultivos (público)
--    B. Territorio   → provincias, cantones y fincas como "áreas" (PostGIS)
--    C. Caché NASA   → lo ya calculado en GEE / POWER / Earthdata
--    D. Resultados   → corridas de análisis, estrategias y revisión experta
--
--  NO se guardan imágenes satelitales ni URLs de teselas GEE (caducan):
--  solo valores agregados por área y mes.
-- =====================================================================

create extension if not exists postgis with schema extensions;
create schema if not exists private;

-- ─────────────────────────────────────────────────────────────────────
-- A. REFERENCIA
-- ─────────────────────────────────────────────────────────────────────

-- Catálogo de fuentes: sirve para la sección "evidencia" de cada estrategia.
create table data_sources (
  id              text primary key,            -- 'gpm_imerg', 'smap_l4', 'nasa_power'...
  name            text not null,
  provider        text not null,               -- 'NASA', 'ESA', 'ISRIC'...
  access          text not null check (access in ('gee','power_api','earthdata','other')),
  dataset_ref     text,                        -- ID GEE o short_name Earthdata
  spatial_res_m   integer,
  temporal_res    text,                        -- 'monthly', '8-day', 'daily', 'static'
  period_start    date,
  period_end      date,
  citation        text,
  url             text
);

-- Variables que medimos y de qué fuente salen.
create table variables (
  id              text primary key,            -- 'precip', 'soil_moisture_root', 'ndvi'...
  name            text not null,
  unit            text not null,
  source_id       text not null references data_sources(id),
  description     text                         -- explicación sencilla para el agricultor
);

-- Catálogo de cultivos (valores base: FAO ECOCROP + FAO-56 para Kc).
create table crops (
  id                    text primary key,      -- 'banano', 'maiz', 'mucuna'...
  name_es               text not null,
  scientific_name       text,
  family                text not null,         -- para cortar ciclos de plagas
  crop_type             text not null check (crop_type in
                          ('cash','staple','legume','cover','perennial','forage')),
  region                text[] default '{}',   -- {'costa','sierra','amazonia'}
  cycle_days            integer,               -- null si es perenne
  is_perennial          boolean default false,
  temp_opt_min_c        numeric, temp_opt_max_c  numeric,
  temp_abs_min_c        numeric, temp_abs_max_c  numeric,
  rain_min_mm_cycle     numeric, rain_max_mm_cycle numeric,
  altitude_max_m        numeric,
  ph_min                numeric, ph_max numeric,
  kc_ini                numeric, kc_mid numeric, kc_end numeric,  -- demanda de agua
  root_depth_m          numeric,
  n_fixing              boolean default false,
  n_fix_kg_ha           numeric,               -- aporte de nitrógeno
  residue_t_ha          numeric,               -- aporte de materia orgánica
  ground_cover          numeric check (ground_cover between 0 and 1),  -- protección vs erosión
  drought_tolerance     smallint check (drought_tolerance between 1 and 5),
  waterlog_tolerance    smallint check (waterlog_tolerance between 1 and 5),
  forage_value          smallint check (forage_value between 0 and 5),
  yield_t_ha            numeric,
  price_usd_t           numeric,
  price_updated_at      date,
  notes                 text,
  source_ref            text
);

-- ─────────────────────────────────────────────────────────────────────
-- B. TERRITORIO
-- ─────────────────────────────────────────────────────────────────────

-- Todo lo que se analiza es un "área": país, provincia, cantón o finca.
-- Así la caché funciona igual para un cantón que para una finca dibujada.
create table areas (
  id              uuid primary key default gen_random_uuid(),
  kind            text not null check (kind in ('country','province','canton','field')),
  name            text not null,
  parent_id       uuid references areas(id) on delete cascade,
  gaul_code       integer,                     -- código FAO GAUL (cantones/provincias)
  geom            extensions.geometry(MultiPolygon, 4326) not null,
  area_ha         numeric generated always as (extensions.st_area(geom::extensions.geography) / 10000) stored,
  owner_id        uuid references auth.users(id) on delete cascade,  -- solo fincas
  created_at      timestamptz default now(),
  constraint field_has_owner check (kind <> 'field' or owner_id is not null)
);
create index areas_geom_idx   on areas using gist (geom);
create index areas_parent_idx on areas (parent_id);
create index areas_owner_idx  on areas (owner_id);

-- Datos que solo el agricultor conoce.
create table field_profiles (
  area_id           uuid primary key references areas(id) on delete cascade,
  irrigation        text check (irrigation in ('none','partial','full')),
  water_source      text,                      -- río, pozo, canal, lluvia
  soil_texture_obs  text,                      -- lo que observa el agricultor
  soil_ph_obs       numeric,                   -- si tiene análisis de laboratorio
  equipment         text[] default '{}',       -- {'tractor','bomba','manual'}
  market_access     text,
  notes             text,
  updated_at        timestamptz default now()
);

-- Rotación actual (la "estrategia 0" que siempre se compara).
create table field_current_rotation (
  id            bigint generated always as identity primary key,
  area_id       uuid not null references areas(id) on delete cascade,
  position      smallint not null,             -- orden en la secuencia
  crop_id       text not null references crops(id),
  start_month   smallint not null check (start_month between 1 and 12),
  months        smallint not null check (months between 1 and 24),
  unique (area_id, position)
);

-- Prioridades del agricultor (0 = no importa, 5 = muy importante).
create table field_priorities (
  area_id          uuid primary key references areas(id) on delete cascade,
  water_saving     smallint default 3 check (water_saving between 0 and 5),
  income           smallint default 3 check (income between 0 and 5),
  soil_health      smallint default 3 check (soil_health between 0 and 5),
  erosion_control  smallint default 3 check (erosion_control between 0 and 5),
  pest_break       smallint default 3 check (pest_break between 0 and 5),
  forage           smallint default 0 check (forage between 0 and 5),
  excluded_crops   text[] default '{}',
  updated_at       timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────────────
-- C. CACHÉ DE DATOS NASA (lo que evita recalcular en GEE)
-- ─────────────────────────────────────────────────────────────────────

-- Características fijas del área (relieve, suelo, cobertura, agua subterránea).
create table area_static_features (
  area_id               uuid primary key references areas(id) on delete cascade,
  elevation_mean_m      numeric,               -- SRTM
  slope_mean_deg        numeric,               -- SRTM
  slope_p90_deg         numeric,
  soil_ph               numeric,               -- OpenLandMap / SoilGrids
  soil_organic_c_gkg    numeric,
  clay_pct              numeric,
  sand_pct              numeric,
  texture_class         text,
  land_cover            jsonb,                 -- {"cropland":0.42,"tree":0.31,...}
  grace_tws_trend_cm_yr numeric,               -- GRACE-FO: tendencia agua almacenada
  computed_at           timestamptz default now()
);

-- Climatología: promedio de cada mes sobre el periodo histórico (12 filas/variable).
create table area_climatology (
  area_id        uuid not null references areas(id) on delete cascade,
  variable_id    text not null references variables(id),
  month          smallint not null check (month between 1 and 12),
  mean           numeric not null,
  p10            numeric,                      -- año seco/frío típico
  p90            numeric,                      -- año húmedo/caliente típico
  n_years        smallint,
  period_start   smallint,                     -- año inicial, ej. 2005
  period_end     smallint,
  computed_at    timestamptz default now(),
  primary key (area_id, variable_id, month)
);

-- Serie mensual real (para anomalías y tendencias). ~240 filas por variable/área.
create table area_monthly_series (
  area_id        uuid not null references areas(id) on delete cascade,
  variable_id    text not null references variables(id),
  month_date     date not null,                -- siempre día 1 del mes
  value          numeric,
  anomaly        numeric,                      -- value - climatología del mes
  primary key (area_id, variable_id, month_date)
);

-- ─────────────────────────────────────────────────────────────────────
-- D. RESULTADOS
-- ─────────────────────────────────────────────────────────────────────

create table analysis_runs (
  id               uuid primary key default gen_random_uuid(),
  area_id          uuid not null references areas(id) on delete cascade,
  kind             text not null check (kind in ('suitability','rotation')),
  requested_by     uuid references auth.users(id) on delete set null,
  params           jsonb not null default '{}',   -- prioridades / rangos usados
  temp_delta_c     numeric default 0,             -- simulador de escenario
  rain_delta_pct   numeric default 0,
  stats            jsonb,                         -- % aptitud, km², etc.
  monthly_calendar jsonb,                         -- riesgo por mes: seco, calor, suelo desnudo
  status           text not null default 'done' check (status in ('pending','done','error')),
  error            text,
  created_at       timestamptz default now()
);
create index analysis_runs_area_idx on analysis_runs (area_id, created_at desc);

-- Cada estrategia comparada (la actual + alternativas).
create table rotation_strategies (
  id               uuid primary key default gen_random_uuid(),
  run_id           uuid not null references analysis_runs(id) on delete cascade,
  rank             smallint not null,
  name             text not null,
  is_current       boolean default false,
  sequence         jsonb not null,               -- [{crop_id,start_month,months}]
  score_total      numeric,
  score_water      numeric,
  score_nitrogen   numeric,
  score_erosion    numeric,
  score_organic    numeric,
  score_pest_break numeric,
  score_income     numeric,
  why              text,                         -- por qué se sugiere
  evidence         jsonb,                        -- [{variable_id,source_id,statement}]
  benefits         text[],
  data_gaps        text[],                       -- qué datos faltan
  risks            text[],                       -- qué debe validar un experto
  unique (run_id, rank)
);

-- Validación por agricultor o agrónomo ("no reemplaza al experto").
create table expert_reviews (
  id             bigint generated always as identity primary key,
  strategy_id    uuid not null references rotation_strategies(id) on delete cascade,
  reviewer_id    uuid references auth.users(id) on delete set null,
  reviewer_role  text check (reviewer_role in ('farmer','agronomist','other')),
  verdict        text check (verdict in ('agree','partial','disagree')),
  comment        text,
  created_at     timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────────────
-- SEGURIDAD (RLS)
--   · El backend usa service_role → salta RLS y escribe la caché.
--   · El frontend usa la anon key → solo lee lo público y sus fincas.
-- ─────────────────────────────────────────────────────────────────────

alter table data_sources           enable row level security;
alter table variables              enable row level security;
alter table crops                  enable row level security;
alter table areas                  enable row level security;
alter table field_profiles         enable row level security;
alter table field_current_rotation enable row level security;
alter table field_priorities       enable row level security;
alter table area_static_features   enable row level security;
alter table area_climatology       enable row level security;
alter table area_monthly_series    enable row level security;
alter table analysis_runs          enable row level security;
alter table rotation_strategies    enable row level security;
alter table expert_reviews         enable row level security;

-- ¿Puede el usuario actual ver esta área? (pública o su propia finca)
create or replace function private.can_read_area(a uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.areas
    where id = a and (kind <> 'field' or owner_id = auth.uid())
  );
$$;

create or replace function private.owns_area(a uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.areas where id = a and owner_id = auth.uid());
$$;

-- Las políticas llaman a estas funciones con el rol del usuario
grant usage on schema private to anon, authenticated;
grant execute on function private.can_read_area(uuid), private.owns_area(uuid) to anon, authenticated;

-- Referencia: lectura pública
create policy "ref read" on data_sources for select using (true);
create policy "ref read" on variables    for select using (true);
create policy "ref read" on crops        for select using (true);

-- Áreas: públicas o propias; el usuario crea/edita solo sus fincas
create policy "areas read"   on areas for select using (kind <> 'field' or owner_id = (select auth.uid()));
create policy "areas insert" on areas for insert with check (kind = 'field' and owner_id = (select auth.uid()));
create policy "areas update" on areas for update using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
create policy "areas delete" on areas for delete using (owner_id = (select auth.uid()));

-- Datos del agricultor: solo el dueño
create policy "owner all" on field_profiles         for all using (private.owns_area(area_id)) with check (private.owns_area(area_id));
create policy "owner all" on field_current_rotation for all using (private.owns_area(area_id)) with check (private.owns_area(area_id));
create policy "owner all" on field_priorities       for all using (private.owns_area(area_id)) with check (private.owns_area(area_id));

-- Caché y resultados: lectura si puede ver el área (escritura solo backend)
create policy "read" on area_static_features for select using (private.can_read_area(area_id));
create policy "read" on area_climatology     for select using (private.can_read_area(area_id));
create policy "read" on area_monthly_series  for select using (private.can_read_area(area_id));
create policy "read" on analysis_runs        for select using (private.can_read_area(area_id));
create policy "read" on rotation_strategies  for select using (
  exists (select 1 from analysis_runs r where r.id = run_id and private.can_read_area(r.area_id))
);

-- Revisiones: cualquiera autenticado puede opinar; cada uno edita lo suyo
create policy "reviews read"   on expert_reviews for select using (true);
create policy "reviews insert" on expert_reviews for insert with check (reviewer_id = (select auth.uid()));
create policy "reviews update" on expert_reviews for update using (reviewer_id = (select auth.uid()));

-- ─────────────────────────────────────────────────────────────────────
-- DATOS SEMILLA: fuentes y variables
-- ─────────────────────────────────────────────────────────────────────

insert into data_sources (id, name, provider, access, dataset_ref, spatial_res_m, temporal_res, period_start, url) values
 ('gpm_imerg',   'GPM IMERG Monthly v07',            'NASA', 'gee',       'NASA/GPM_L3/IMERG_MONTHLY_V07',     11000, 'monthly', '2000-06-01', 'https://gpm.nasa.gov/data/imerg'),
 ('smap_l4',     'SMAP L4 Soil Moisture',            'NASA', 'gee',       'NASA/SMAP/SPL4SMGP/008',             11000, '3-hourly','2015-03-31', 'https://smap.jpl.nasa.gov'),
 ('modis_ndvi',  'MODIS Terra NDVI (MOD13Q1)',       'NASA', 'gee',       'MODIS/061/MOD13Q1',                  250,   '16-day',  '2000-02-18', 'https://lpdaac.usgs.gov/products/mod13q1v061/'),
 ('modis_lst',   'MODIS Terra LST (MOD11A2)',        'NASA', 'gee',       'MODIS/061/MOD11A2',                  1000,  '8-day',   '2000-02-18', 'https://lpdaac.usgs.gov/products/mod11a2v061/'),
 ('modis_et',    'MODIS Evapotranspiration (MOD16A2)','NASA','gee',       'MODIS/061/MOD16A2GF',                500,   '8-day',   '2000-01-01', 'https://lpdaac.usgs.gov/products/mod16a2gfv061/'),
 ('nasa_power',  'NASA POWER Agroclimatology',       'NASA', 'power_api', 'AG community',                       55000, 'daily',   '1981-01-01', 'https://power.larc.nasa.gov'),
 ('grace_fo',    'GRACE/GRACE-FO Mascon',            'NASA', 'gee',       'NASA/GRACE/MASS_GRIDS_V04/MASCON',   55000, 'monthly', '2002-04-01', 'https://grace.jpl.nasa.gov'),
 ('srtm',        'SRTM 30 m',                        'NASA', 'gee',       'USGS/SRTMGL1_003',                   30,    'static',  null,         'https://www.earthdata.nasa.gov/sensors/srtm'),
 ('ecostress',   'ECOSTRESS LST',                    'NASA', 'earthdata', 'ECO_L2T_LSTE',                       70,    'irregular','2018-07-01','https://ecostress.jpl.nasa.gov'),
 ('soilgrids',   'OpenLandMap / SoilGrids',          'ISRIC','gee',       'OpenLandMap/SOL',                    250,   'static',  null,         'https://soilgrids.org'),
 ('esa_wc',      'ESA WorldCover 10 m',              'ESA',  'gee',       'ESA/WorldCover/v200',                10,    'static',  null,         'https://esa-worldcover.org');

insert into variables (id, name, unit, source_id, description) values
 ('precip',              'Lluvia mensual',                   'mm/mes',  'gpm_imerg',  'Cuánta agua cae del cielo cada mes.'),
 ('heavy_rain_days',     'Días de lluvia intensa (>50 mm)',  'días/mes','gpm_imerg',  'Días con aguaceros que pueden causar erosión o inundación.'),
 ('soil_moisture_surf',  'Humedad del suelo superficial',    'm³/m³',   'smap_l4',    'Agua en los primeros 5 cm del suelo.'),
 ('soil_moisture_root',  'Humedad en zona de raíces',        'm³/m³',   'smap_l4',    'Agua disponible para las raíces (0–100 cm).'),
 ('ndvi',                'Verdor de la vegetación (NDVI)',   'índice',  'modis_ndvi', 'Qué tan verde y activa está la vegetación; bajo = suelo desnudo o estrés.'),
 ('lst_day',             'Temperatura de superficie (día)',  '°C',      'modis_lst',  'Qué tan caliente está el suelo/cultivo a mediodía.'),
 ('et_actual',           'Evapotranspiración real',          'mm/mes',  'modis_et',   'Agua que pierde el campo por evaporación y transpiración.'),
 ('t2m',                 'Temperatura del aire media',       '°C',      'nasa_power', 'Temperatura promedio a 2 m del suelo.'),
 ('t2m_max',             'Temperatura máxima',               '°C',      'nasa_power', 'Temperatura más alta del día, promedio mensual.'),
 ('t2m_min',             'Temperatura mínima',               '°C',      'nasa_power', 'Temperatura más baja del día; clave para riesgo de helada.'),
 ('frost_days',          'Días con helada (Tmín < 2 °C)',    'días/mes','nasa_power', 'Días con riesgo de helada (importante en la Sierra).'),
 ('rh2m',                'Humedad relativa',                 '%',       'nasa_power', 'Humedad del aire; alta favorece hongos.'),
 ('solar_rad',           'Radiación solar',                  'MJ/m²/día','nasa_power','Energía solar disponible para la fotosíntesis.'),
 ('et0',                 'Evapotranspiración de referencia', 'mm/mes',  'nasa_power', 'Cuánta agua "pide" la atmósfera; base para calcular el riego.'),
 ('water_balance',       'Balance hídrico (lluvia − ET₀)',   'mm/mes',  'gpm_imerg',  'Negativo = el cultivo necesita riego ese mes.');
