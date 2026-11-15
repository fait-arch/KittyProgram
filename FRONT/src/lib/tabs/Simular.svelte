<script lang="ts">
	// POST /predict — what-if con lluvia, temperatura e índices de El Niño
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { pct, usd, num, signed, RISK_COLORS, RISK_LABEL } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	let { id }: { id: string } = $props();

	let base = $state('normal');
	let adj = $state({ temp_delta_c: 0, rain_delta_pct: 0, nino12_anom: 0, oni: 0 });
	let useEnso = $state(false);
	const SLIDERS = [
		{ k: 'temp_delta_c', label: 'Temperatura', min: -3, max: 4, step: 0.5, unit: '°C', enso: false },
		{ k: 'rain_delta_pct', label: 'Lluvia', min: -50, max: 100, step: 5, unit: '%', enso: false },
		{ k: 'nino12_anom', label: 'Mar frente a Ecuador (Niño 1+2)', min: -3, max: 6, step: 0.5, unit: '°C', enso: true },
		{ k: 'oni', label: 'Índice ONI', min: -3, max: 3.5, step: 0.5, unit: '', enso: true }
	] as const;
	const PRESETS = [
		{ label: 'Niño fuerte', v: { temp_delta_c: 0.5, rain_delta_pct: 60, nino12_anom: 3, oni: 2 }, e: true },
		{ label: 'Sequía', v: { temp_delta_c: 1, rain_delta_pct: -35, nino12_anom: 0, oni: 0 }, e: false },
		{ label: '2050 cálido', v: { temp_delta_c: 2, rain_delta_pct: 10, nino12_anom: 0, oni: 0 }, e: false }
	];

	let result = $state<Promise<any> | null>(null);
	$effect(() => {
		const body = { area_id: id, crop: app.crop, base_scenario: base, adjust: { temp_delta_c: adj.temp_delta_c, rain_delta_pct: adj.rain_delta_pct, ...(useEnso ? { nino12_anom: adj.nino12_anom, oni: adj.oni } : {}) } };
		const t = setTimeout(() => (result = api.predict(body)), 300);
		return () => clearTimeout(t);
	});
	const reset = () => { adj = { temp_delta_c: 0, rain_delta_pct: 0, nino12_anom: 0, oni: 0 }; useEnso = false; };
</script>

<Section title="¿Y si el clima cambia así?" hint="El modelo recalcula la pérdida con tus ajustes">
	<div class="row"><small>Partir de</small><Segmented options={[{ id: 'normal', label: 'Año normal' }, { id: 'nino', label: 'Año Niño' }, { id: 'nina', label: 'Año Niña' }]} bind:value={base} size="sm" /></div>
	<div class="row">{#each PRESETS as p}<button class="btn sm" onclick={() => { adj = { ...p.v }; useEnso = p.e; }}>{p.label}</button>{/each}<button class="btn sm" onclick={reset}>Reiniciar</button></div>
	<div class="sl">
		{#each SLIDERS as s}
			{#if !s.enso || useEnso}
				<label>
					<span class="spread"><span>{s.label}</span><b>{signed(adj[s.k])} {s.unit}</b></span>
					<input type="range" min={s.min} max={s.max} step={s.step} bind:value={adj[s.k]} />
				</label>
			{/if}
		{/each}
		<label class="chk"><input type="checkbox" bind:checked={useEnso} /> Fijar también los índices de El Niño</label>
	</div>
</Section>

<Async promise={result} height={160}>
	{#snippet children(r: any)}
		<div class="res card" style="--c:{RISK_COLORS[r.risk_class]}">
			<div class="kpi">
				<div class="label">Pérdida simulada</div>
				<div class="value big">{pct(r.loss_pct)}</div>
				<div class="sub">{pct(r.loss_pct_low)} – {pct(r.loss_pct_high)} · {RISK_LABEL[r.risk_class]}</div>
			</div>
			<div class="kpi right">
				<div class="label">vs. {base}</div>
				<div class="value" class:tag-bad={r.delta_vs_base_pct > 0} class:tag-ok={r.delta_vs_base_pct < 0}>{signed(r.delta_vs_base_pct)} pts</div>
				<div class="sub">{usd(r.loss_usd)} · {num(r.loss_t)} t</div>
			</div>
		</div>
		{#if r.top_factors?.length}<p class="muted">Lo que más pesa: {r.top_factors.map((f: any) => f.label).join(' · ')}</p>{/if}
		{#if r.warning}<p class="err">⚠ {r.warning}</p>{/if}
		<p class="disclaimer">{r.synthetic ? 'Predictor sintético (el modelo .joblib aún no está cargado). ' : ''}Modelo {r.model?.name}</p>
	{/snippet}
</Async>

<style>
	.sl { display: flex; flex-direction: column; gap: 0.9rem; margin-top: 0.4rem; }
	.sl label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.88rem; }
	.sl b { font-variant-numeric: tabular-nums; }
	.chk { flex-direction: row !important; align-items: center; gap: 0.45rem !important; color: var(--ink-2); cursor: pointer; }
	.res { display: flex; justify-content: space-between; gap: 1rem; border-left: 4px solid var(--c); }
	.big { font-size: 2.2rem !important; color: var(--c); }
	.right { text-align: right; }
</style>
