-- 0008 — Política explícita "solo backend" en las tablas internas (etl_runs, training_samples).
-- Equivale a no tener acceso (ya se revocaron los privilegios en 0007); documenta la intención
-- y evita el aviso "RLS enabled, no policy" del revisor de Supabase.
create policy "solo backend" on public.etl_runs         for all to anon, authenticated using (false) with check (false);
create policy "solo backend" on public.training_samples for all to anon, authenticated using (false) with check (false);
