<script lang="ts">
	// /areas/{id}/climate (escenario vs normal) + /areas/{id}/series + /areas/{id}/hazards
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { MONTHS, num } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Chart from '#lib/charts/Chart.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	let { id }: { id: string } = $props();

	const VARS = 't2m,precip,rh_mean,heavy_rain_days,saturated_days';
	const clim = $derived(Promise.all([api.climate(id, app.scenario, VARS), app.scenario === 'normal' ? null : api.climate(id, 'normal', VARS)]));

	let variable = $state('precip');
	const VOPTS = [{ id: 'precip', label: 'Lluvia' }, { id: 't2m', label: 'Temperatura' }, { id: 'rh_mean', label: 'Humedad' }];
	let from = $state('2015-01');
	const series = $derived(api.series(id, { variables: 'precip,t2m,ndvi', from, anomaly: true }));
	const hazards = $derived(api.hazards(id, from));
	const ranges = [{ id: '2001-01', label: '2001–hoy' }, { id: '2015-01', label: '2015–hoy' }, { id: '2021-01', label: '2021–hoy' }];
	const NAMES: Record<string, string> = { precip: 'Lluvia', t2m: 'Temperatura', rh_mean: 'Humedad', ndvi: 'Verdor (NDVI)' };
</script>

<Section title="Cómo es el año en este escenario" hint="Climatología mensual comparada con un año normal">
	<Segmented options={VOPTS} bind:value={variable} size="sm" />
	<Async promise={clim} height={200}>
		{#snippet children([c, n]: any)}
			{@const v = c.variables[variable]}
			{@const vn = n?.variables?.[variable]}
			{#if v}
				<Chart
					labels={MONTHS}
					unit={v.unit}
					series={[
						{ name: 'Escenario', color: '#a99f6a', values: v.months.map((m: any) => m.mean), type: variable === 'precip' ? 'bar' : 'line', low: variable === 'precip' ? undefined : v.months.map((m: any) => m.min), high: variable === 'precip' ? undefined : v.months.map((m: any) => m.max) },
						...(vn ? [{ name: 'Año normal', color: '#9aa39b', values: vn.months.map((m: any) => m.mean), type: (variable === 'precip' ? 'bar' : 'line') as 'bar' | 'line', dashed: true }] : [])
					]}
				/>
				<div class="grid3">
					{#each Object.entries(c.variables as Record<string, any>) as [k, x]}
						<div class="kpi"><div class="label">{({ t2m: 'Temp. media', precip: 'Lluvia anual', rh_mean: 'Humedad', heavy_rain_days: 'Días de aguacero', saturated_days: 'Suelo saturado' } as any)[k] ?? k}</div>
						<div class="value sm">{num(x.annual, 1)}</div>
						{#if n?.variables?.[k]}<div class="sub">normal {num(n.variables[k].annual, 1)}</div>{/if}</div>
					{/each}
				</div>
				<small>{v.method === 'composite' ? `Promedio de ${v.n_members} años` : v.method}</small>
			{/if}
		{/snippet}
	</Async>
</Section>

<Section title="Lo observado por satélite" hint="Anomalía = diferencia con lo habitual para ese mes">
	<Segmented options={ranges} bind:value={from} size="sm" />
	<Async promise={series} height={190}>
		{#snippet children(s: any)}
			{#each Object.entries(s as Record<string, any[]>) as [k, rows]}
				{#if rows?.length}
					<div>
						<h4>{NAMES[k] ?? k}</h4>
						<Chart labels={rows.map((r: any) => r.month.slice(0, 4))} ticks={6} height={130} zeroLine
							series={[{ name: 'Anomalía', color: k === 'ndvi' ? '#3d8f6a' : k === 't2m' ? '#a99f6a' : '#2f7f73', values: rows.map((r: any) => r.anomaly ?? r.value), type: 'bar' }]}
							format={(v) => (k === 'ndvi' ? v.toFixed(2) : v.toFixed(0))} />
					</div>
				{/if}
			{/each}
		{/snippet}
	</Async>
</Section>

<Section title="Eventos extremos por mes" hint="Días de aguacero, humedad alta y suelo saturado">
	<Async promise={hazards} height={190}>
		{#snippet children(h: any[])}
			<Chart labels={h.map((r) => r.month.slice(0, 4))} ticks={6} unit="días"
				series={[
					{ name: 'Humedad ≥ 80 %', color: '#2f7f73', values: h.map((r) => r.humid_days) },
					{ name: 'Suelo saturado', color: '#7d8a80', values: h.map((r) => r.saturated_days) },
					{ name: 'Aguacero ≥ 50 mm', color: '#a99f6a', values: h.map((r) => r.heavy_rain_days), type: 'bar' },
					{ name: 'Días > 32 °C', color: '#963a25', values: h.map((r) => r.hot_days), dashed: true }
				]} format={(v) => v.toFixed(0)} />
			{@const worst = [...h].sort((a, b) => b.heavy_rain_days - a.heavy_rain_days)[0]}
			{#if worst}<p class="muted">Mes más extremo: <b>{worst.month}</b> con {worst.heavy_rain_days} aguaceros y {worst.max_consecutive_wet_days} días seguidos de lluvia.</p>{/if}
		{/snippet}
	</Async>
</Section>

<style>
	h4 { margin: 0.2rem 0; font-size: 0.82rem; font-weight: 600; }
	.value.sm { font-size: 1.05rem; }
</style>
