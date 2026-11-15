<script lang="ts">
	// /areas/{id}/risk + /crops/{crop}/phenology + /crops/{crop}/pathogens + /areas/{id}/risk/history
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { MONTHS, PATHOGEN_LABEL, PATHOGEN_COLOR } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import RiskHeatmap from '#lib/charts/RiskHeatmap.svelte';
	import Chart from '#lib/charts/Chart.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	let { id }: { id: string } = $props();

	const risk = $derived.by(() => { void app.refresh; return api.risk(id, app.scenario, app.crop); });
	let region = $state<string | undefined>(undefined);
	$effect(() => { api.area(id, app.crop).then((a: any) => (region = a.region)).catch(() => {}); });
	const pheno = $derived(api.phenology(app.crop, region));
	const pathogens = $derived(api.pathogens(app.crop));

	let pathogen = $state('monilia');
	let from = $state('2001-01');
	const history = $derived(api.riskHistory(id, pathogen, from));
	const STAGE: Record<string, string> = { floracion: 'Floración', desarrollo_mazorca: 'Desarrollo de mazorca', cosecha_principal: 'Cosecha principal', cosecha_secundaria: 'Cosecha secundaria' };
	const ranges = [{ id: '2001-01', label: 'Desde 2001' }, { id: '2014-01', label: 'Desde 2014' }, { id: '2020-01', label: 'Desde 2020' }];
</script>

<Async promise={Promise.all([risk, pheno])} height={140}>
	{#snippet children([r, ph]: any)}
		{@const win = [...new Set(ph.filter((p: any) => p.is_risk_window).flatMap((p: any) => p.months))] as number[]}
		<Section title="Riesgo de enfermedad por mes" hint="Escenario seleccionado · 0 = sin riesgo, 1 = condiciones ideales para el hongo">
			<RiskHeatmap months={r.months} pathogens={r.pathogens} riskWindow={win} />
			{#if r.peak}<p class="muted">Pico: <b>{PATHOGEN_LABEL[r.peak.pathogen]}</b> en <b>{MONTHS[r.peak.month - 1]}</b> ({Math.round(r.peak.risk * 100)} %).</p>{/if}
		</Section>
		<Section title="Calendario del cultivo">
			<div class="cal">
				{#each ph as p}
					<span class="st">{STAGE[p.stage] ?? p.stage}</span>
					<div class="months">{#each MONTHS as m, i}<i class:on={p.months.includes(i + 1)} class:risk={p.is_risk_window && p.months.includes(i + 1)} title={m}></i>{/each}</div>
				{/each}
			</div>
		</Section>
	{/snippet}
</Async>

<Section title="Lo que pasó en años anteriores" hint="Riesgo observado mes a mes y el índice ONI de El Niño">
	{#snippet aside()}
		<select bind:value={pathogen} aria-label="Enfermedad">{#each Object.entries(PATHOGEN_LABEL) as [k, v]}<option value={k}>{v}</option>{/each}</select>
	{/snippet}
	<Segmented options={ranges} bind:value={from} size="sm" />
	<Async promise={history} height={190}>
		{#snippet children(h: any[])}
			<Chart
				labels={h.map((x) => x.month.slice(0, 4))}
				ticks={7}
				series={[
					{ name: PATHOGEN_LABEL[pathogen], color: PATHOGEN_COLOR[pathogen], values: h.map((x) => x.risk_index), type: 'area' },
					{ name: 'ONI (eje der.)', color: '#4d7484', values: h.map((x) => x.oni), axis: 'right', dashed: true }
				]}
				bands={h.flatMap((x, i) => (x.oni >= 0.5 ? [{ from: i, to: i, color: '#8b5e3c' }] : []))}
				format={(v) => v.toFixed(1)}
			/>
			<small>Sombreado = meses con El Niño (ONI ≥ 0.5)</small>
		{/snippet}
	</Async>
</Section>

<Async promise={pathogens} height={80}>
	{#snippet children(ps: any[])}
		<details>
			<summary>¿Cómo sabemos que un día favorece al hongo?</summary>
			<ul>
				{#each ps as p}<li><b>{p.name_es}</b> <i>({p.scientific_name})</i>: {p.rule_text}. {p.description ?? ''} {#if !p.validated}<span class="pill">por validar</span>{/if}</li>{/each}
			</ul>
		</details>
	{/snippet}
</Async>

<style>
	.cal { display: grid; grid-template-columns: 9.5rem 1fr; gap: 0.35rem 0.75rem; align-items: center; font-size: 0.82rem; }
	.months { display: grid; grid-template-columns: repeat(12, 1fr); gap: 3px; }
	.months i { height: 10px; border-radius: 3px; background: var(--surface-2); }
	.months i.on { background: color-mix(in srgb, var(--accent) 45%, transparent); }
	.months i.risk { background: var(--accent-2); }
	details { font-size: 0.85rem; color: var(--ink-2); }
	details ul { padding-left: 1.1rem; display: flex; flex-direction: column; gap: 0.4rem; }
	summary { cursor: pointer; }
</style>
