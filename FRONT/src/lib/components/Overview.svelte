<script lang="ts">
	// Panel flotante izquierdo: totales (/losses/summary) + ranking (/losses) + buscador (/areas).
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { num, pct, usd, RISK_COLORS, RISK_LABEL, signed } from '#lib/fmt';
	import Async from './Async.svelte';

	let open = $state(false);
	let q = $state('');
	let areas = $state<any[]>([]);

	const summary = $derived.by(() => { void app.refresh; return api.lossesSummary({ scenario: app.scenario, province: app.province || undefined, crop: app.crop, vs: app.scenario === 'normal' ? '' : 'normal' }); });
	const ranking = $derived.by(() => { void app.refresh; return open ? api.losses({ scenario: app.scenario, province: app.province || undefined, crop: app.crop }) : null; });
	$effect(() => { api.areas({ province: app.province || undefined, has_crop: app.crop }).then((a) => (areas = a)).catch(() => {}); });
	const matches = $derived(q.length > 1 ? areas.filter((a) => a.name.toLowerCase().includes(q.toLowerCase())).slice(0, 6) : []);
	function pick(a: any) { app.select(a.id, a.name); q = ''; }
</script>

<aside class="ov card">
	<div class="search">
		<input type="text" placeholder="Buscar cantón cacaotero…" bind:value={q} aria-label="Buscar cantón" />
		{#if matches.length}
			<ul>{#each matches as a}<li><button onclick={() => pick(a)}>{a.name} <small>{a.province?.name} · {num(a.crop_ha)} ha</small></button></li>{/each}</ul>
		{/if}
	</div>

	<Async promise={summary} height={150}>
		{#snippet children(s: any)}
			<div class="scope"><small>{s.scope?.name ?? 'Ecuador'} · {num(s.totals.exposed_ha)} ha de cacao</small></div>
			<div class="hero">
				<div class="kpi">
					<div class="label">Pérdida estimada</div>
					<div class="value">{usd(s.totals.loss_usd)}</div>
					<div class="sub">{num(s.totals.loss_t)} t <span class="muted">({num(s.totals.loss_t_low)}–{num(s.totals.loss_t_high)})</span></div>
				</div>
				{#if s.vs}
					<div class="kpi">
						<div class="label">vs. año normal</div>
						<div class="value" class:tag-bad={s.vs.delta_usd > 0}>{signed(s.vs.delta_usd, (x) => usd(x))}</div>
						<div class="sub">{signed(s.vs.delta_t, (x) => num(x))} t</div>
					</div>
				{/if}
			</div>
			{#if s.by_class}
				{@const total = Object.values(s.by_class as Record<string, number>).reduce((a, b) => a + b, 0)}
				<div class="cls">
				<div class="bar" title="Cantones por clase de riesgo">
					{#each ['bajo', 'medio', 'alto', 'muy_alto'] as k}
						{#if s.by_class[k]}<span style="flex:{s.by_class[k]};background:{RISK_COLORS[k]}" title="{RISK_LABEL[k]}: {s.by_class[k]}"></span>{/if}
					{/each}
				</div>
				<small>{total} cantones · {Object.entries(s.by_class).map(([k, v]) => `${v} ${RISK_LABEL[k]?.toLowerCase()}`).join(' · ')}</small>
				</div>
			{/if}
			<div class="top">
				<h3>Más afectados</h3>
				{#each s.top_areas.slice(0, 3) as t}
					<button class="tl" onclick={() => app.select(t.area_id, t.name)}><span>{t.name}</span><b>{usd(t.loss_usd)}</b></button>
				{/each}
			</div>
		{/snippet}
	</Async>

	<button class="btn sm more" onclick={() => (open = !open)}>{open ? 'Ocultar ranking' : 'Ver todos los cantones'}</button>
	{#if open}
		<div class="rank">
			<Async promise={ranking} height={120}>
				{#snippet children(r: any)}
					<table>
						<thead><tr><th>Cantón</th><th>Pérdida</th><th>USD</th></tr></thead>
						<tbody>
							{#each [...r.items].sort((a, b) => b.loss_pct - a.loss_pct) as it}
								<tr class="clickable" class:on={app.selectedId === it.area_id} onclick={() => app.select(it.area_id, it.name)}>
									<td><i style="background:{RISK_COLORS[it.risk_class]}"></i>{it.name}</td>
									<td>{pct(it.loss_pct)}</td>
									<td>{usd(it.loss_usd)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
					<small>Modelo {r.model?.name}</small>
				{/snippet}
			</Async>
		</div>
	{/if}
</aside>

<style>
	.ov { position: absolute; top: 20px; left: 20px; z-index: 3; width: 330px; max-height: calc(100% - 300px); min-height: 0; overflow: auto; display: flex; flex-direction: column; gap: 1rem; box-shadow: var(--shadow); padding: 1.1rem; border-top: 4px solid var(--accent); }
	.search { position: relative; }
	.search input { width: 100%; border-radius: 999px; padding-left: 0.9rem; background: var(--accent-soft); border-color: transparent; }
	.search input:focus { outline: 2px solid var(--accent); background: #fff; }
	.search ul { position: absolute; left: 0; right: 0; top: calc(100% + 4px); list-style: none; margin: 0; padding: 0.3rem; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow); z-index: 5; }
	.search li button { width: 100%; text-align: left; border: 0; background: none; padding: 0.45rem 0.6rem; border-radius: 8px; cursor: pointer; display: flex; justify-content: space-between; gap: 0.5rem; }
	.search li button:hover { background: var(--surface-2); }
	.hero { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.4rem; }
	.bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; gap: 2px; margin-top: 0.9rem; }
	.top { margin-top: 1rem; display: flex; flex-direction: column; gap: 0.15rem; }
	.top h3 { font-size: 0.78rem; color: var(--accent); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.2rem; }
	.tl { display: flex; justify-content: space-between; border: 0; background: none; padding: 0.35rem 0; cursor: pointer; border-bottom: 1px solid var(--line); }
	.tl:last-child { border-bottom: 0; }
	.tl:hover span { color: var(--accent); }
	.more { align-self: flex-start; }
	td i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 0.4rem; }
	tr.on td { background: var(--surface-2); font-weight: 600; }
	@media (max-width: 900px) {
		.ov { top: auto; bottom: 12px; left: 12px; right: 12px; width: auto; max-height: 42vh; padding: 0.9rem; gap: 0.6rem; }
		.top, .more, .rank, .cls, .scope { display: none; }
		.hero { margin-top: 0; }
		.ov :global(.kpi .value) { font-size: 1.25rem; }
	}
</style>
