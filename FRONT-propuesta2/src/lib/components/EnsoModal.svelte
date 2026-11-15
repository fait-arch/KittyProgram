<script lang="ts">
	let { page = false }: { page?: boolean } = $props();
	// /enso/current + /enso/history + /enso/events + /enso/years
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { ENSO_LABEL, INTENSITY } from '#lib/fmt';
	import Modal from './Modal.svelte';
	import Async from './Async.svelte';
	import Section from './Section.svelte';
	import Chart from '#lib/charts/Chart.svelte';
	import Segmented from './Segmented.svelte';

	let from = $state('1995-01');
	let phase = $state('');
	const current = api.ensoCurrent();
	const hist = $derived(api.ensoHistory(from));
	const events = $derived(api.ensoEvents((phase || undefined) as any, Number(from.slice(0, 4))));
	const years = api.ensoYears();
	const ranges = [{ id: '1980-01', label: '1980' }, { id: '1995-01', label: '1995' }, { id: '2010-01', label: '2010' }];
	function idxOf(months: string[], m: string) {
		const k = m?.slice(0, 7), i = months.indexOf(k);
		if (i >= 0) return i;
		return k > months[months.length - 1] ? months.length - 1 : 0;
	}
	const C: Record<string, string> = { nino: '#a99f6a', nina: '#2f7f73', neutral: '#b5b8ae' };
</script>

<Modal title="El Niño en Ecuador" wide {page} kicker="El Niño" onclose={() => (app.modal = null)}>
	<Async promise={current} height={70}>
		{#snippet children(e: any)}
			<div class="now" style="--c:{C[e.phase]}">
				<div>
					<small>Ahora · {e.source}</small>
					<h3>{ENSO_LABEL[e.phase]} {INTENSITY[e.intensity] ?? ''}</h3>
					<p>{e.message_es}</p>
				</div>
				<div class="grid2 n">
					<div class="kpi"><div class="label">ONI {e.oni?.season}</div><div class="value">{e.oni?.value?.toFixed(2)}</div></div>
					<div class="kpi"><div class="label">Niño 1+2</div><div class="value">{e.nino12_anom?.value > 0 ? '+' : ''}{e.nino12_anom?.value?.toFixed(1)} °C</div></div>
				</div>
			</div>
		{/snippet}
	</Async>

	<Section title="Historia del océano" hint="ONI (Pacífico central) y Niño 1+2 (frente a Ecuador). Bandas = eventos identificados">
		{#snippet aside()}<Segmented options={ranges} bind:value={from} size="sm" />{/snippet}
		<Async promise={Promise.all([hist, events])} height={220}>
			{#snippet children([h, ev]: any)}
				{@const months = h.oni.map((x: any) => x.month)}
				{@const n12 = new Map(h.nino12_anom?.map((x: any) => [x.month, x.value]) ?? [])}
				<Chart labels={months.map((m: string) => m.slice(0, 4))} ticks={10} height={150} zeroLine
					series={[
						{ name: 'ONI', color: '#5f9b84', values: h.oni.map((x: any) => x.value) },
						{ name: 'Niño 1+2 (°C)', color: '#a99f6a', values: months.map((m: string) => n12.get(m) ?? null), dashed: true }
					]}
					bands={ev.map((e: any) => ({ from: idxOf(months, e.start_month), to: e.end_month ? idxOf(months, e.end_month) : months.length - 1, color: C[e.phase], label: e.id }))}
					format={(v) => v.toFixed(1)} />
			{/snippet}
		</Async>
	</Section>

	<div class="cols">
		<Section title="Eventos">
			{#snippet aside()}<Segmented options={[{ id: '', label: 'Todos' }, { id: 'nino', label: 'Niño' }, { id: 'nina', label: 'Niña' }]} bind:value={phase} size="sm" />{/snippet}
			<Async promise={events} height={120}>
				{#snippet children(ev: any[])}
					<table>
						<thead><tr><th>Evento</th><th>Inicio</th><th>Pico ONI</th><th>Intensidad</th></tr></thead>
						<tbody>{#each ev as e}<tr><td><i style="background:{C[e.phase]}"></i>{ENSO_LABEL[e.phase]}{e.is_coastal ? ' costero' : ''}</td><td>{e.start_month?.slice(0, 7)}</td><td>{e.peak_oni ?? '—'}</td><td>{INTENSITY[e.intensity] ?? e.intensity}</td></tr>{/each}</tbody>
					</table>
				{/snippet}
			</Async>
		</Section>
		<Section title="Cada año, ¿qué fue?" hint="Clasificación ene–jun, época que define la cosecha">
			<Async promise={years} height={120}>
				{#snippet children(ys: any[])}
					<div class="years">
						{#each ys as y}<span style="background:{C[y.enso_class]}" class:coast={y.is_coastal_nino} title="{y.year}: {ENSO_LABEL[y.enso_class]}{y.is_coastal_nino ? ' costero' : ''} · ONI {y.oni_jan_jun} · Niño1+2 {y.nino12_anom_jan_jun}">{String(y.year).slice(2)}</span>{/each}
					</div>
					<small><i class="sw" style="background:{C.nino}"></i>Niño <i class="sw" style="background:{C.nina}"></i>Niña <i class="sw" style="background:{C.neutral}"></i>Neutral · borde = Niño costero</small>
				{/snippet}
			</Async>
		</Section>
	</div>
</Modal>

<style>
	.now { display: flex; justify-content: space-between; gap: 1.5rem; border-left: 4px solid var(--c); padding-left: 1rem; flex-wrap: wrap; }
	.now h3 { font-family: var(--display); font-size: 1.4rem; }
	.n { min-width: 220px; }
	.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
	td i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
	.years { display: grid; grid-template-columns: repeat(auto-fill, minmax(30px, 1fr)); gap: 3px; }
	.years span { color: #fff; font-size: 0.7rem; text-align: center; padding: 0.25rem 0; border-radius: 4px; }
	.years span.coast { outline: 2px solid var(--ink); outline-offset: -2px; }
	.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 0.25rem 0 0.6rem; vertical-align: -1px; }
	@media (max-width: 700px) { .cols { grid-template-columns: 1fr; } }
</style>
