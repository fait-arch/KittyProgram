<script lang="ts">
	// Barras apiladas al 100 %: cuántos cantones caen en cada nivel de pérdida, por escenario.
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { LOSS_RAMP, LOSS_CLASSES, lossLevel } from '#lib/fmt';

	const SC = [
		{ id: 'normal', label: 'Año normal' },
		{ id: 'nina', label: 'La Niña' },
		{ id: 'nino', label: 'Año Niño' },
		{ id: 'actual', label: 'Temporada actual' },
		{ id: 'nino_extremo', label: 'Niño extremo' },
		{ id: 'ssp245_2050', label: '2050 moderado' },
		{ id: 'ssp585_2050', label: '2050 alto' }
	];
	let rows = $state<{ id: string; label: string; counts: number[]; n: number }[]>([]);
	$effect(() => {
		const prov = app.province, crop = app.crop;
		Promise.all(SC.map((s) => api.losses({ scenario: s.id, province: prov || undefined, crop }).then((r: any) => {
			const counts = [0, 0, 0, 0, 0];
			for (const i of r.items ?? []) { const l = lossLevel(i.loss_pct); if (l >= 0) counts[l]++; }
			return { ...s, counts, n: counts.reduce((a, b) => a + b, 0) };
		}).catch(() => null))).then((x) => (rows = x.filter((r): r is NonNullable<typeof r> => !!r && r.n > 0)));
	});
	let hover = $state<string | null>(null);
</script>

<div class="mix">
	{#each rows as r}
		<button class="r" class:on={r.id === app.scenario} onclick={() => (app.scenario = r.id)} onmouseenter={() => (hover = r.id)} onmouseleave={() => (hover = null)} title="Usar este escenario">
			<span class="n">{r.label}</span>
			<span class="bar">
				{#each r.counts as c, i}
					{#if c}<i style="flex:{c};background:{LOSS_RAMP[i]}" title="{LOSS_CLASSES[i].label}: {c} cantones"></i>{/if}
				{/each}
			</span>
			<span class="v">{hover === r.id ? r.counts.map((c, i) => (c ? `${c} ${LOSS_CLASSES[i].label.toLowerCase()}` : '')).filter(Boolean).join(' · ') : `${r.n} cantones`}</span>
		</button>
	{/each}
	{#if !rows.length}<div class="skeleton" style="min-height:180px"></div>{/if}
	<div class="leg">
		{#each LOSS_CLASSES as c, i}<span><i style="background:{LOSS_RAMP[i]}"></i>{c.label} <small>{c.range}</small></span>{/each}
	</div>
</div>

<style>
	.mix { display: flex; flex-direction: column; gap: 0.35rem; }
	.r { display: grid; grid-template-columns: 130px 1fr 170px; align-items: center; gap: 0.7rem; border: 0; background: none; padding: 0.3rem 0.4rem; border-radius: 10px; cursor: pointer; text-align: left; color: inherit; }
	.r:hover { background: var(--surface-2); }
	.r.on .n { font-weight: 700; color: var(--accent); }
	.n { font-size: 0.86rem; }
	.bar { display: flex; height: 16px; border-radius: 5px; overflow: hidden; gap: 2px; background: var(--surface-2); }
	.v { font-size: 0.76rem; color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.leg { display: flex; flex-wrap: wrap; gap: 0.4rem 0.9rem; margin-top: 0.4rem; font-size: 0.78rem; }
	.leg i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 0.3rem; vertical-align: -1px; }
	.leg small { color: var(--ink-2); }
	@media (max-width: 640px) { .r { grid-template-columns: 95px 1fr; } .v { display: none; } }
</style>
