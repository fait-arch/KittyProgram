-- 06_observaciones — seed de pruebas (ver supabase/seed/README.md)
insert into public.field_observations (area_id, pathogen_id, observed_on, lat, lon, source, external_id, notes) values
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','3968709595','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','3968711538','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','3968713662','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.56,-79.52,'gbif','3968714491','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','3968714492','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','3968715551','GBIF: MATERIAL_SAMPLE'),
('50c3f374-d390-5f9c-af38-68ebcc64def6','monilia','2016-10-03',-2.96,-79.65,'gbif','3968715552','GBIF: MATERIAL_SAMPLE'),
('d97358e3-3f8c-5758-b5a9-1db8e4f55845','monilia','2016-10-03',-2.55,-79.52,'gbif','5863496651','GBIF: MATERIAL_SAMPLE'),
(NULL,'escoba_bruja','2026-10-02',0.0678,-79.1496,'gbif','6869090480','GBIF: HUMAN_OBSERVATION'),
('f68c040f-7ee9-5934-94ec-f2f83a9599b3','escoba_bruja','1990-08-01',-1.105,-79.4558,'gbif','4930328475','GBIF: PRESERVED_SPECIMEN'),
('f68c040f-7ee9-5934-94ec-f2f83a9599b3','escoba_bruja','1990-09-01',-1.105,-79.4558,'gbif','4930328478','GBIF: PRESERVED_SPECIMEN'),
(NULL,'escoba_bruja','1940-11-24',-2.358,-80.6569,'gbif','4099469390','GBIF: PRESERVED_SPECIMEN') on conflict (source, external_id) do nothing;
insert into public.etl_runs (script, params, status, rows_written, notes) values
('seed_pruebas','{"sample": false, "years": "2001-2025"}','done',115290,'Carga de datos reales (ver supabase/seed/README.md)');
