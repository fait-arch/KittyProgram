-- Funciones RPC para crear/editar fincas desde GeoJSON.
-- PostgREST no convierte GeoJSON → geometry al insertar, por eso se usan RPC.
-- SECURITY INVOKER: corren con el rol del usuario, así que RLS sigue aplicando.

create or replace function public.create_field(
  p_name     text,
  p_geojson  jsonb,
  p_parent   uuid default null
) returns public.areas
language sql security invoker set search_path = '' as $$
  insert into public.areas (kind, name, parent_id, geom, owner_id)
  values (
    'field',
    p_name,
    p_parent,
    extensions.st_multi(extensions.st_setsrid(extensions.st_geomfromgeojson(p_geojson::text), 4326)),
    auth.uid()
  )
  returning *;
$$;

create or replace function public.update_field_geom(
  p_id       uuid,
  p_geojson  jsonb
) returns public.areas
language sql security invoker set search_path = '' as $$
  update public.areas
     set geom = extensions.st_multi(extensions.st_setsrid(extensions.st_geomfromgeojson(p_geojson::text), 4326))
   where id = p_id and kind = 'field'
  returning *;
$$;

revoke execute on function public.create_field(text, jsonb, uuid)  from public, anon;
revoke execute on function public.update_field_geom(uuid, jsonb)   from public, anon;
grant  execute on function public.create_field(text, jsonb, uuid)  to authenticated, service_role;
grant  execute on function public.update_field_geom(uuid, jsonb)   to authenticated, service_role;
