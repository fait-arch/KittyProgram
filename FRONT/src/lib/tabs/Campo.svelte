<script lang="ts">
	// GET /observations?area_id= + POST /observations (🔒 sesión Supabase)
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { PATHOGEN_LABEL, errMsg } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	let { id }: { id: string } = $props();

	let source = $state('');
	let reload = $state(0);
	const list = $derived.by(() => { void reload; void app.refresh; return api.observations({ area_id: id, source: source || undefined, limit: 200 }); });
	const SRC = [{ id: '', label: 'Todas' }, { id: 'gbif', label: 'GBIF' }, { id: 'tecnico', label: 'Técnicos' }, { id: 'agricultor', label: 'Agricultores' }];

	let form = $state({ pathogen_id: 'monilia', observed_on: new Date().toISOString().slice(0, 10), lat: '', lon: '', pods_total: '', pods_diseased: '', severity: '', role: 'agricultor', notes: '' });
	let msg = $state(''), err = $state(''), busy = $state(false);

	$effect(() => {
		api.area(id).then((a: any) => { if (!form.lat && a.centroid) { form.lat = String(a.centroid.lat); form.lon = String(a.centroid.lon); } }).catch(() => {});
	});
	function gps() {
		navigator.geolocation?.getCurrentPosition(({ coords }) => { form.lat = coords.latitude.toFixed(5); form.lon = coords.longitude.toFixed(5); });
	}
	const n = (v: string) => (v === '' ? null : Number(v));
	async function submit(e: SubmitEvent) {
		e.preventDefault();
		msg = err = ''; busy = true;
		try {
			const r: any = await api.createObservation({ ...form, lat: Number(form.lat), lon: Number(form.lon), pods_total: n(form.pods_total), pods_diseased: n(form.pods_diseased), severity: n(form.severity), notes: form.notes || null }, app.token);
			msg = `Observación guardada${r?.area_id && r.area_id !== id ? ' (en otro cantón según su ubicación)' : ''}. ¡Gracias!`;
			form.notes = ''; form.pods_total = ''; form.pods_diseased = ''; form.severity = '';
			reload++; app.refresh++;
		} catch (x) { err = errMsg(x); } finally { busy = false; }
	}
</script>

<Section title="Lo que se ha visto en el campo" hint="Reportes de técnicos, agricultores y registros GBIF">
	<Segmented options={SRC} bind:value={source} size="sm" />
	<Async promise={list} height={120}>
		{#snippet children(rows: any[])}
			{#if !rows.length}<p class="muted">Aún no hay reportes aquí. ¡Sé el primero!</p>{:else}
				<table>
					<thead><tr><th>Fecha</th><th>Enfermedad</th><th>Incidencia</th><th>Fuente</th></tr></thead>
					<tbody>
						{#each rows as o}
							<tr title={o.notes ?? ''}><td>{o.observed_on}</td><td>{PATHOGEN_LABEL[o.pathogen_id] ?? o.pathogen_id ?? '—'}</td><td>{o.incidence_pct != null ? `${o.incidence_pct} %` : o.pods_total ? `${o.pods_diseased}/${o.pods_total}` : '—'}</td><td>{o.source}</td></tr>
						{/each}
					</tbody>
				</table>
			{/if}
		{/snippet}
	</Async>
</Section>

<Section title="Reportar lo que veo" hint="Ayuda a validar el modelo con datos reales">
	{#if !app.token}
		<div class="card soft">
			<p>Para reportar necesitas una cuenta de técnico o agricultor.</p>
			<button class="btn primary" onclick={() => (app.modal = 'login')}>Iniciar sesión</button>
		</div>
	{:else}
		<form class="f" onsubmit={submit}>
			<label>Enfermedad<select bind:value={form.pathogen_id}>{#each Object.entries(PATHOGEN_LABEL) as [k, v]}<option value={k}>{v}</option>{/each}</select></label>
			<label>Fecha<input type="date" bind:value={form.observed_on} required /></label>
			<label>Latitud<input type="number" step="any" bind:value={form.lat} required /></label>
			<label>Longitud<input type="number" step="any" bind:value={form.lon} required /></label>
			<button type="button" class="btn sm full" onclick={gps}>◎ Usar mi ubicación</button>
			<label>Mazorcas revisadas<input type="number" min="0" bind:value={form.pods_total} /></label>
			<label>Mazorcas enfermas<input type="number" min="0" bind:value={form.pods_diseased} /></label>
			<label>Severidad (0–5)<input type="number" min="0" max="5" bind:value={form.severity} /></label>
			<label>Soy<select bind:value={form.role}><option value="agricultor">Agricultor</option><option value="tecnico">Técnico</option></select></label>
			<label class="full">Notas<textarea rows="2" bind:value={form.notes} maxlength="2000"></textarea></label>
			<button class="btn primary full" disabled={busy}>{busy ? 'Enviando…' : 'Enviar reporte'}</button>
			{#if msg}<p class="full tag-ok">{msg}</p>{/if}
			{#if err}<p class="full err">{err}</p>{/if}
		</form>
	{/if}
</Section>

<style>
	.soft { background: var(--surface-2); border: 0; display: flex; flex-direction: column; gap: 0.6rem; align-items: flex-start; }
	.f { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; }
	.f label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8rem; color: var(--ink-2); }
	.f input, .f select, .f textarea { color: var(--ink); }
	.full { grid-column: 1 / -1; justify-content: center; }
</style>
