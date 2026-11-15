<script lang="ts">
	// /areas/{id}/detail + /areas/{id} (terreno)
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { num, pct, usd, signed, RISK_COLORS, RISK_LABEL, PATHOGEN_LABEL, STATUS_ICON } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	let { id }: { id: string } = $props();

	const detail = $derived.by(() => { void app.refresh; return api.detail(id, app.scenario, app.crop); });
	const area = $derived(api.area(id, app.crop));
	$effect(() => { detail.then((d: any) => (app.selectedName = d.area.name)).catch(() => {}); });
</script>

<Async promise={detail} height={260}>
	{#snippet children(d: any)}
		{@const L = d.loss}
		<div class="hero" style="--c:{RISK_COLORS[L?.risk_class] ?? '#999'}">
			<div class="kpi">
				<div class="label">Pérdida esperada de cosecha</div>
				<div class="value big">{pct(L?.loss_pct)}</div>
				<div class="range"><span style="left:{L?.loss_pct_low}%;width:{(L?.loss_pct_high ?? 0) - (L?.loss_pct_low ?? 0)}%"></span><b style="left:{L?.loss_pct}%"></b></div>
				<div class="sub">rango probable {pct(L?.loss_pct_low)} – {pct(L?.loss_pct_high)}</div>
			</div>
			<span class="pill risk">{RISK_LABEL[L?.risk_class] ?? '—'}</span>
		</div>
		<div class="grid3">
			<div class="kpi"><div class="label">Dinero</div><div class="value">{usd(L?.loss_usd)}</div></div>
			<div class="kpi"><div class="label">Toneladas</div><div class="value">{num(L?.loss_t)}</div></div>
			<div class="kpi"><div class="label">Hectáreas</div><div class="value">{num(L?.exposed_ha)}</div></div>
		</div>
		{#if L?.vs_normal}
			<p class="vs">Frente a un año normal: <b class:tag-bad={L.vs_normal.delta_pct > 0}>{signed(L.vs_normal.delta_pct)} puntos</b> de pérdida y <b>{signed(L.vs_normal.delta_usd, (x) => usd(x))}</b>.</p>
		{/if}

		<Section title="¿Por qué?" hint="Factores que más pesan en la estimación del modelo">
			{@const max = Math.max(...d.top_factors.map((f: any) => f.contribution_pct), 1)}
			<div class="factors">
				{#each d.top_factors as f}
					<div><span>{f.label}</span><small>{f.value ?? ''}</small></div>
					<div class="fb"><i style="width:{(f.contribution_pct / max) * 70}px"></i><small>+{f.contribution_pct} pts</small></div>
				{/each}
			</div>
			<p class="muted">Enfermedad dominante: <b>{PATHOGEN_LABEL[d.dominant_pathogen] ?? d.dominant_pathogen}</b>{#if d.peak_risk}, pico en el mes {d.peak_risk.month}{/if}.</p>
		</Section>

		<Section title="¿El clima le sienta al cacao?" hint="Comparado con los requerimientos ECOCROP">
			<ul class="req">
				{#each d.requirement_check as r}
					<li><span class="tag-{r.status}">{STATUS_ICON[r.status]}</span><span>{r.label}</span><b>{num(r.value, 1)} {r.unit}</b><small>óptimo {r.opt?.[0] ?? '…'}–{r.opt?.[1] ?? '…'}</small></li>
				{/each}
			</ul>
			{#if d.suitability}<p>Aptitud: <b>{d.suitability.class}</b> ({d.suitability.score?.toFixed(2)})</p>{/if}
		</Section>

		<Async promise={area} height={90}>
			{#snippet children(a: any)}
				{#if a.static}
					<Section title="Terreno">
						<div class="grid3 terr">
							<div><small>Altitud</small><b>{num(a.static.elevation_mean_m)} m</b></div>
							<div><small>Pendiente</small><b>{num(a.static.slope_mean_deg, 1)}°</b></div>
							<div><small>pH suelo</small><b>{num(a.static.soil_ph, 1)}</b></div>
							<div><small>Arcilla</small><b>{num(a.static.clay_pct)} %</b></div>
							<div><small>Arena</small><b>{num(a.static.sand_pct)} %</b></div>
							<div><small>C orgánico</small><b>{num(a.static.soil_organic_c_gkg, 1)} g/kg</b></div>
						</div>
					</Section>
				{/if}
			{/snippet}
		</Async>

		{#if d.data_gaps?.length}
			<details><summary>Lo que aún no sabemos ({d.data_gaps.length})</summary><ul>{#each d.data_gaps as g}<li>{g}</li>{/each}</ul></details>
		{/if}
		<p class="disclaimer">{d.disclaimer} · Modelo {d.model?.name}{#if d.model?.mae} (error medio ±{d.model.mae} pts){/if}</p>
	{/snippet}
</Async>

<style>
	.hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
	.hero .kpi { flex: 1; }
	.big { font-size: 2.6rem !important; color: var(--c); }
	.risk { background: var(--c); color: #fff; }
	.range { position: relative; height: 6px; background: var(--surface-2); border-radius: 3px; margin: 0.5rem 0 0.3rem; max-width: 260px; }
	.range span { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--c) 40%, transparent); border-radius: 3px; }
	.range b { position: absolute; top: -3px; width: 3px; height: 12px; background: var(--c); border-radius: 2px; }
	.vs { color: var(--ink-2); }
	.factors { display: grid; grid-template-columns: 1fr 130px; gap: 0.5rem 0.8rem; align-items: center; font-size: 0.85rem; }
	.factors small { margin-left: 0.35rem; }
	.fb { display: flex; align-items: center; gap: 0.4rem; white-space: nowrap; }
	.fb i { flex-shrink: 1; min-width: 4px; max-width: 70px; }
	.fb i { height: 8px; background: var(--accent); border-radius: 4px; display: block; }
	.req { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
	.req li { display: grid; grid-template-columns: 1.1rem 1fr auto; gap: 0 0.5rem; align-items: baseline; }
	.req small { grid-column: 2 / -1; font-size: 0.75rem; }
	.terr div { display: flex; flex-direction: column; }
	details { font-size: 0.85rem; color: var(--ink-2); }
	summary { cursor: pointer; }
</style>
