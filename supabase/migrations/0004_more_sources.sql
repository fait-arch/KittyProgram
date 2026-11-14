-- Fuentes adicionales: ERA5-Land, GLDAS, HLS, NEX-GDDP-CMIP6, FAO GAEZ
-- y variables nuevas (estrés ECOSTRESS y escenarios CMIP6).
-- Temperatura, heladas y ET₀ pasan a calcularse con ERA5-Land (≈9 km), que
-- representa mejor la Costa que NASA POWER (≈55 km). POWER queda como respaldo.

insert into public.data_sources (id, name, provider, access, dataset_ref, spatial_res_m, temporal_res, period_start, url, citation) values
 ('era5_land',  'ERA5-Land (diario y mensual)',            'ECMWF/Copernicus', 'gee',       'ECMWF/ERA5_LAND/DAILY_AGGR',        9000,  'daily',   '1950-01-01', 'https://cds.climate.copernicus.eu', 'Contains modified Copernicus Climate Change Service information'),
 ('gldas',      'GLDAS 2.1 Noah',                          'NASA',             'gee',       'NASA/GLDAS/V021/NOAH/G025/T3H',     27000, '3-hourly','2000-01-01', 'https://ldas.gsfc.nasa.gov/gldas', null),
 ('hls',        'Harmonized Landsat Sentinel-2 (HLS) v2',  'NASA',             'gee',       'NASA/HLS/HLSL30/v002 + NASA/HLS/HLSS30/v002', 30, '2-3 days', '2013-04-01', 'https://hls.gsfc.nasa.gov', null),
 ('gddp_cmip6', 'NEX-GDDP-CMIP6',                          'NASA',             'gee',       'NASA/GDDP-CMIP6',                   27000, 'daily',   '1950-01-01', 'https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6', null),
 ('gaez',       'FAO GAEZ v4',                             'FAO',              'other',     'gaez.fao.org Data Viewer',          9000,  'static',  null,         'https://gaez.fao.org', null)
on conflict (id) do nothing;

update public.data_sources
   set dataset_ref = 'AppEEARS: ECO_L2T_LSTE.002 (LST), ECO_L3T_JET.002 (ETdaily), ECO_L4T_ESI.002 (ESI)',
       url = 'https://appeears.earthdatacloud.nasa.gov'
 where id = 'ecostress';

insert into public.variables (id, name, unit, source_id, description) values
 ('esi',               'Índice de estrés evaporativo (ESI)',  'índice', 'ecostress',  'Qué tan estresada por falta de agua está la vegetación (bajo = más estrés).'),
 ('temp_change_c',     'Cambio proyectado de temperatura',    '°C',     'gddp_cmip6', 'Diferencia entre el clima futuro proyectado (2041–2060) y el histórico (1995–2014).'),
 ('precip_change_pct', 'Cambio proyectado de lluvia',         '%',      'gddp_cmip6', 'Cuánto más o menos llovería cada mes en el futuro según modelos climáticos.'),
 ('soil_moisture_long','Humedad del suelo (serie 2000→)',     'kg/m²',  'gldas',      'Agua en la zona de raíces, serie larga para tendencias.')
on conflict (id) do nothing;

update public.variables set source_id = 'era5_land'
 where id in ('t2m', 't2m_max', 't2m_min', 'frost_days', 'et0');
