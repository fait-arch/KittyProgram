<script lang="ts">
	// /compare (mismo cantón en los 6 escenarios) + /areas/{id}/suitability
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { pct, usd, RISK_COLORS, PATHOGEN_LABEL } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	let { id }: { id: string } = $props();

	const ALL = 'normal,nina,nino,actual,ssp245_2050,ssp585_2050';
	const NAME: Record<string, string> = { normal: 'Año normal', nina: 'La Niña', nino: 'El Niño', actual: 'Temporada actual', ssp245_2050: '2050 moderado', ssp585_2050: '2050 alto' };
	const cmp = $derived.by(() => { void app.refresh; return api.compare(id, ALL, app.crop); });
	const suit = $derived(api.suitability(id, app.crop, ALL));
	const SUIT_C: Record<string, string> = { apta: 'var(--good)', marginal: 'var(--warn)', no_apta: 'var(--bad)' };
</script>

<Section title="El mismo cantón, seis futuros" hint="Pérdida esperada con su rango probable">
	<Async promise={cmp} height={220}>
		{#snippet children(c: any)}
			{@const max = Math.max(...c.items.map((i: any) => i.loss?.loss_pct_high ?? 0), 10)}
			<div class="bars">
				{#each c.items as it}
					{@const L = it.loss}
					<button class="b" class:on={it.scenario === app.scenario} onclick={() => (app.scenario = it.scenario)} title="Usar este escenario en el mapa">
						<span class="n">{NAME[it.scenario] ?? it.scenario}</span>
						<span class="track">
							{#if L}
								<i class="rng" style="left:{(L.loss_pct_low / max) * 100}%;width:{((L.loss_pct_high - L.loss_pct_low) / max) * 100}%;background:{RISK_COLORS[L.risk_class]}"></i>
								<i class="pt" style="left:{(L.loss_pct / max) * 100}%;background:{RISK_COLORS[L.risk_class]}"></i>
							{/if}
						</span>
						<span class="v"><b>{pct(L?.loss_pct)}</b><small>{usd(L?.loss_usd)}</small></span>
					</button>
				{/each}
			</div>
			<table>
				<thead><tr><th>Escenario</th><th>Enfermedad</th><th>Lluvia</th><th>Temp.</th></tr></thead>
				<tbody>
					{#each c.items as it}
						<tr><td>{NAME[it.scenario]}</td><td>{PATHOGEN_LABEL[it.dominant_pathogen] ?? '—'}</td><td>{it.climate?.precip?.annual?.toFixed(0) ?? '—'} mm</td><td>{it.climate?.t2m?.annual?.toFixed(1) ?? '—'} °C</td></tr>
					{/each}
				</tbody>
			</table>
		{/snippet}
	</Async>
</Section>

<Section title="¿Seguirá siendo tierra de cacao?" hint="Aptitud climática ECOCROP (0 a 1)">
	<Async promise={suit} height={150}>
		{#snippet children(s: any[])}
			<div class="suit">
				{#each s as x}
					<span>{NAME[x.scenario] ?? x.scenario}</span>
					<span class="track"><i style="width:{x.score * 100}%;background:{SUIT_C[x.class] ?? 'var(--accent)'}"></i></span>
					<span class="cls" style="color:{SUIT_C[x.class]}">{x.class} {x.score.toFixed(2)}</span>
					{#if x.limiting_factors?.length}<small class="lim">Limita: {x.limiting_factors.join(', ')}</small>{/if}
				{/each}
			</div>
		{/snippet}
	</Async>
</Section>

<style>
	.bars { display: flex; flex-direction: column; gap: 0.3rem; }
	.b { display: grid; grid-template-columns: 7.5rem 1fr 5.5rem; gap: 0.75rem; align-items: center; border: 0; background: none; padding: 0.45rem 0.4rem; border-radius: 10px; cursor: pointer; text-align: left; }
	.b:hover, .b.on { background: var(--surface-2); }
	.b.on .n { font-weight: 600; }
	.n { font-size: 0.85rem; }
	.track { position: relative; height: 10px; background: var(--surface-2); border-radius: 5px; }
	.b.on .track { background: var(--surface); }
	.rng { position: absolute; top: 0; bottom: 0; opacity: 0.35; border-radius: 5px; }
	.pt { position: absolute; top: -3px; width: 4px; height: 16px; border-radius: 2px; transform: translateX(-2px); }
	.v { display: flex; flex-direction: column; align-items: flex-end; }
	.v small { color: var(--ink-2); font-size: 0.75rem; }
	.suit { display: grid; grid-template-columns: 7.5rem 1fr 6rem; gap: 0.35rem 0.75rem; align-items: center; font-size: 0.85rem; }
	.suit .track i { display: block; height: 100%; border-radius: 5px; }
	.cls { text-align: right; font-weight: 600; text-transform: capitalize; }
	.lim { grid-column: 2 / -1; margin-top: -0.25rem; }
</style>
