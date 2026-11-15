<script lang="ts">
	// GET /point/climate (NASA POWER en vivo) + /areas/lookup para saltar al cantón
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { MONTHS, num, STATUS_ICON } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Chart from '#lib/charts/Chart.svelte';
	let { lat, lon }: { lat: number; lon: number } = $props();
	const data = $derived(api.pointClimate(lat, lon, app.crop));
	const lookup = $derived(api.lookup(lat, lon).catch(() => null));
</script>

<Async promise={lookup} height={40}>
	{#snippet children(l: any)}
		{#if l?.canton}
			<div class="card soft spread">
				<span>Este punto está en <b>{l.canton.name}</b>, {l.province?.name}</span>
				<button class="btn sm primary" onclick={() => app.select(l.canton.id, l.canton.name)}>Ver cantón →</button>
			</div>
		{:else}
			<p class="muted">Este punto está fuera de los cantones con datos precalculados.</p>
		{/if}
	{/snippet}
</Async>

<Async promise={data} height={260} loadingText="Consultando NASA POWER…">
	{#snippet children(d: any)}
		<div class="grid3">
			<div class="kpi"><div class="label">Temp. media</div><div class="value">{num(d.annual?.t2m, 1)} °C</div></div>
			<div class="kpi"><div class="label">Lluvia anual</div><div class="value">{num(d.annual?.precip_mm)} mm</div></div>
			<div class="kpi"><div class="label">Humedad</div><div class="value">{num(d.annual?.rh2m)} %</div></div>
		</div>
		<Section title="Clima típico del año" hint="{d.source} · celda de {d.resolution_km} km{d.elevation_m ? ` · ${num(d.elevation_m)} m` : ''}">
			<Chart labels={MONTHS} unit="mm" unitRight="°C"
				series={[
					{ name: 'Lluvia', color: '#2f7f73', values: MONTHS.map((_, i) => d.precip_mm_month?.[String(i + 1)] ?? null), type: 'bar' },
					{ name: 'Temperatura', color: '#a99f6a', values: MONTHS.map((_, i) => d.monthly_climatology?.T2M?.[String(i + 1)] ?? null), axis: 'right', low: MONTHS.map((_, i) => d.monthly_climatology?.T2M_MIN?.[String(i + 1)] ?? null), high: MONTHS.map((_, i) => d.monthly_climatology?.T2M_MAX?.[String(i + 1)] ?? null) }
				]} />
		</Section>
		<Section title="¿Sirve para cacao?">
			<ul class="req">
				{#each d.requirement_check ?? [] as r}
					<li><span class="tag-{r.status}">{STATUS_ICON[r.status]}</span><span>{r.label}</span><b>{num(r.value, 1)} {r.unit}</b></li>
				{/each}
			</ul>
		</Section>
		{#if d.warning}<p class="disclaimer">⚠ {d.warning}</p>{/if}
	{/snippet}
</Async>

<style>
	.soft { background: var(--surface-2); border: 0; }
	.req { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
	.req li { display: grid; grid-template-columns: 1.1rem 1fr auto; gap: 0.5rem; }
</style>
