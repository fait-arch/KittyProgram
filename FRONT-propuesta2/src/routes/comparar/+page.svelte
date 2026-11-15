<script lang="ts">
	// Comparar: el mismo cantón en cada escenario (mapas pequeños + rango), aptitud y zonas 2050.
	import { goto } from '$app/navigation';
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { pct, usd, num, lossColor, lossLabel, ZONE_COLORS, ZONE_LABEL } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import MiniMap from '#lib/charts/MiniMap.svelte';
	import ClassMix from '#lib/charts/ClassMix.svelte';
	import Comparar from '#lib/tabs/Comparar.svelte';

	const SC = [
		{ id: 'normal', label: 'Año normal (neutro)', sub: 'Promedio 2001–2025' },
		{ id: 'nino', label: 'Año Niño', sub: 'Promedio 2001–2025' },
		{ id: 'nino_extremo', label: 'Niño costero extremo', sub: 'Como 1983 o 1998' },
		{ id: 'actual', label: 'Temporada en curso', sub: 'Con El Niño de hoy' },
		{ id: 'ssp245_2050', label: '2050 · emisiones moderadas', sub: 'NASA NEX-GDDP-CMIP6' },
		{ id: 'ssp585_2050', label: '2050 · emisiones altas', sub: 'NASA NEX-GDDP-CMIP6' }
	];

	let cantons = $state<any[]>([]);
	$effect(() => { api.areas({ kind: 'canton' }).then((a) => (cantons = a.sort((x: any, y: any) => x.name.localeCompare(y.name)))).catch(() => {}); });
	let id = $state(app.selectedId ?? '');
	$effect(() => { if (!id && cantons.length) id = (cantons.find((c) => /vinces/i.test(c.name)) ?? cantons[0]).id; });
	const cur = $derived(cantons.find((c) => c.id === id));
	const provName = $derived(cur?.province?.name ?? cur?.province ?? '');

	// Cantones de la provincia (contexto de los mapas pequeños)
	let geo = $state<any[]>([]);
	$effect(() => { if (provName) api.areasGeojson({ province: provName }).then((fc: any) => (geo = fc.features)).catch(() => {}); });
	let colorsBy = $state<Record<string, Map<string, string>>>({});
	let zoneColors = $state(new Map<string, string>());
	$effect(() => {
		const p = provName, crop = app.crop;
		if (!p) return;
		for (const s of SC) api.losses({ scenario: s.id, province: p, crop }).then((r: any) => {
			colorsBy = { ...colorsBy, [s.id]: new Map(r.items.map((i: any) => [i.area_id, lossColor(i.loss_pct)])) };
		}).catch(() => {});
		api.zones(app.future, crop, p).then((z: any) => (zoneColors = new Map(z.items.map((i: any) => [i.area_id, ZONE_COLORS[i.zone_class] ?? '#8a948c'])))).catch(() => {});
	});
	const cmp = $derived(id ? api.compare(id, SC.map((s) => s.id).join(','), app.crop) : null);
	const zones = $derived(id ? api.zones(app.future, app.crop, provName || undefined) : null);
	function pick(cid: string) { id = cid; }
</script>

<svelte:head><title>CacaoResiliente · Comparar</title></svelte:head>

<div class="pg">
	<header class="top">
		<div>
			<small>Comparar escenarios</small>
			<h1>El mismo cantón en cada escenario</h1>
			<p class="muted">Pérdida estimada por el modelo en un año normal, un año Niño, un Niño costero extremo (1983, 1998), la temporada actual y el clima de 2041–2060.</p>
		</div>
		<label class="sel">Cantón
			<select bind:value={id}>
				{#each cantons as c}<option value={c.id}>{c.name} · {c.province?.name ?? ''}</option>{/each}
			</select>
		</label>
	</header>

	<Async promise={cmp} height={300}>
		{#snippet children(c: any)}
			<div class="cards">
				{#each SC as s}
					{@const it = c.items.find((x: any) => x.scenario === s.id)}
					{@const L = it?.loss}
					<article class="card sc" class:on={s.id === app.scenario}>
						<header><b>{s.label}</b><small>{s.sub}</small></header>
						<div class="mm">
							{#if geo.length}<MiniMap features={geo} colors={colorsBy[s.id] ?? new Map()} selectedId={id} onpick={pick} />{:else}<div class="skeleton" style="min-height:150px"></div>{/if}
						</div>
						{#if L}
							<div class="v" style="--c:{lossColor(L.loss_pct)}"><span class="big">{pct(L.loss_pct)}</span><span class="pill lv">{lossLabel(L.loss_pct)}</span></div>
							<small class="muted">Rango {pct(L.loss_pct_low)} – {pct(L.loss_pct_high)}{L.loss_usd != null ? ` · ${usd(L.loss_usd)}` : ''}</small>
							{#if L.inherited_from}<small class="muted">Estimación por zona (índice de {L.inherited_from})</small>{/if}
						{:else}
							<p class="muted">Sin estimación para este escenario.</p>
						{/if}
						<button class="lnk" onclick={() => { app.scenario = s.id; app.select(id, cur?.name ?? ''); goto('/'); }}><Icon name="map" size={15} /> Ver en el mapa</button>
					</article>
				{/each}
			</div>
		{/snippet}
	</Async>

	<div class="grid2">
		<section class="card box">
			{#if id}{#key id}<Comparar {id} />{/key}{/if}
		</section>
		<div class="col">
			<section class="card box">
				<h3>Zonas 2050 en {provName || 'la provincia'}</h3>
				<p class="muted">Aptitud del clima × riesgo de El Niño ({app.future === 'ssp585_2050' ? 'emisiones altas' : 'emisiones moderadas'})</p>
				{#if geo.length}<MiniMap features={geo} colors={zoneColors} selectedId={id} height={210} onpick={pick} />{/if}
				<div class="leg">{#each Object.entries(ZONE_COLORS) as [k, col]}<span><i style="background:{col}"></i>{ZONE_LABEL[k]}</span>{/each}</div>
				<Async promise={zones} height={30}>
					{#snippet children(z: any)}
						{@const me = z.items.find((i: any) => i.area_id === id)}
						{#if me}<p>{cur?.name}: <b style="color:{ZONE_COLORS[me.zone_class]}">{ZONE_LABEL[me.zone_class]}</b> · aptitud {num(me.suitability_now, 2)} → {num(me.suitability_future, 2)}</p>{/if}
					{/snippet}
				</Async>
			</section>
			<section class="card box">
				<h3>Cantones por nivel en cada escenario</h3>
				<ClassMix />
			</section>
		</div>
	</div>
</div>

<style>
	.pg { max-width: 1180px; margin: 0 auto; padding: 1.6rem 1.4rem 3rem; display: flex; flex-direction: column; gap: 1.1rem; }
	.top { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; }
	.top > div { flex: 1; min-width: 280px; display: flex; flex-direction: column; gap: 0.3rem; }
	.top small { font: 600 0.72rem/1 var(--font); text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-2); }
	.top h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); }
	.sel { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.78rem; color: var(--ink-2); min-width: 260px; }
	.sel select { color: var(--ink); font-size: 0.95rem; font-weight: 600; }
	.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem; }
	.sc { display: flex; flex-direction: column; gap: 0.4rem; box-shadow: var(--shadow); }
	.sc.on { outline: 2px solid var(--accent); }
	.sc header { display: flex; flex-direction: column; }
	.sc header small { color: var(--ink-2); }
	.mm { border-radius: 10px; overflow: hidden; background: var(--map-sea); padding: 0.3rem; }
	.v { display: flex; align-items: center; gap: 0.6rem; }
	.big { font-family: var(--display); font-size: 1.9rem; font-weight: 700; color: var(--heading); }
	.lv { background: var(--c); color: #2b221c; }
	.lnk { border: 0; background: none; padding: 0; margin-top: auto; color: var(--accent); font-weight: 600; cursor: pointer; display: inline-flex; gap: 0.3rem; align-items: center; align-self: flex-start; }
	.grid2 { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 0.8rem; align-items: start; }
	.col { display: flex; flex-direction: column; gap: 0.8rem; }
	.box { display: flex; flex-direction: column; gap: 0.6rem; box-shadow: var(--shadow); }
	.box h3 { font-family: var(--display); font-size: 1.05rem; color: var(--heading); }
	.leg { display: flex; flex-wrap: wrap; gap: 0.4rem 0.9rem; font-size: 0.8rem; }
	.leg i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 0.3rem; vertical-align: -1px; }
	@media (max-width: 1000px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } .grid2 { grid-template-columns: 1fr; } }
	@media (max-width: 640px) { .pg { padding: 1rem 0.9rem 2rem; } .cards { grid-template-columns: 1fr; } }
</style>
