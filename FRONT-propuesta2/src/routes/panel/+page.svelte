<script lang="ts">
	// Panel general: cifras clave, alerta principal, El Niño hoy, cacao y gráficos por escenario.
	import { goto } from '$app/navigation';
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { num, pct, usd, signed, lossColor, ENSO_LABEL, INTENSITY } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import Chart from '#lib/charts/Chart.svelte';
	import ClassMix from '#lib/charts/ClassMix.svelte';

	const prov = $derived(app.province || undefined);
	const summary = $derived(api.lossesSummary({ scenario: app.scenario, province: prov, crop: app.crop, vs: app.scenario === 'normal' ? '' : 'normal' }));
	const losses = $derived(api.losses({ scenario: app.scenario, province: prov, crop: app.crop }));
	const normal = $derived(api.losses({ scenario: 'normal', province: prov, crop: app.crop }));
	const enso = api.ensoCurrent();
	const zones = $derived(api.zones('ssp245_2050', app.crop, prov));
	const alerts = $derived(api.alerts('actual', prov, app.crop));

	// Pérdida total por escenario (barras)
	const SC = [['normal', 'Normal'], ['nina', 'Niña'], ['nino', 'Niño'], ['actual', 'Hoy'], ['nino_extremo', 'Niño extr.'], ['ssp245_2050', '2050 mod.'], ['ssp585_2050', '2050 alto']];
	let bars = $state<{ labels: string[]; t: (number | null)[]; usd: (number | null)[] } | null>(null);
	$effect(() => {
		const p = prov, crop = app.crop;
		Promise.all(SC.map(([id]) => api.lossesSummary({ scenario: id, province: p, crop }).then((s: any) => s.totals).catch(() => null)))
			.then((r) => (bars = { labels: SC.map(([, l]) => l), t: r.map((x: any) => x?.loss_t ?? null), usd: r.map((x: any) => (x?.loss_usd != null ? x.loss_usd / 1e6 : null)) }));
	});

	// Cantones donde más sube la pérdida frente a un año normal
	// Por provincia: los cantones heredan el índice de su provincia, así que listarlos repetiría el mismo valor
	const provL = $derived(api.losses({ scenario: app.scenario, kind: 'province', crop: app.crop }));
	const provN = $derived(api.losses({ scenario: 'normal', kind: 'province', crop: app.crop }));
	const rising = $derived(Promise.all([provL, provN]).then(([l, n]: any[]) => {
		const base = new Map(n.items.map((i: any) => [i.area_id, i.loss_pct]));
		return l.items.map((i: any) => ({ ...i, delta: i.loss_pct - ((base.get(i.area_id) as number) ?? i.loss_pct) }))
			.sort((a: any, b: any) => b.delta - a.delta).slice(0, 12);
	}));
	const open = (id: string, name: string) => { app.select(id, name); goto('/'); };
</script>

<svelte:head><title>CacaoResiliente · Panel</title></svelte:head>

<div class="pg">
	<header class="ph">
		<small>Panel general · {app.province || 'Costa y Amazonía del Ecuador'}</small>
		<h1>¿Cómo va el cacao esta temporada?</h1>
	</header>

	<Async promise={summary} height={130}>
		{#snippet children(s: any)}
			<div class="kpis">
				<div class="card kpi k"><span class="ic"><Icon name="farm" /></span><div class="value">{num(s.totals.loss_t)} t</div><div class="label">Cacao perdido</div>{#if s.vs}<div class="sub">{signed(s.vs.delta_t, (x) => num(x))} t frente a un año normal</div>{/if}</div>
				<div class="card kpi k"><span class="ic"><Icon name="download" /></span><div class="value">{usd(s.totals.loss_usd)}</div><div class="label">Valor en riesgo</div>{#if s.vs}<div class="sub">{signed(s.vs.delta_usd, (x) => usd(x))} frente a un año normal</div>{/if}</div>
				<Async promise={losses} height={110}>
					{#snippet children(l: any)}
						{@const r = l.items.filter((i: any) => i.loss_pct > 30).length}
						<div class="card kpi k"><span class="ic"><Icon name="bell" /></span><div class="value" class:tag-bad={r > 0}>{r} de {l.items.length}</div><div class="label">Cantones en alerta roja</div><div class="sub">Pérdida mayor a 30 % (IPC 4–5)</div></div>
					{/snippet}
				</Async>
				<Async promise={enso} height={110}>
					{#snippet children(e: any)}
						<div class="card kpi k"><span class="ic"><Icon name="wave" /></span><div class="value">{e.oni?.value > 0 ? '+' : ''}{e.oni?.value?.toFixed(2)}</div><div class="label">Índice ONI · {ENSO_LABEL[e.phase] ?? e.phase}</div><div class="sub">Niño 1+2: {e.nino12_anom?.value > 0 ? "+" : ""}{e.nino12_anom?.value?.toFixed(1)} °C · NOAA</div></div>
					{/snippet}
				</Async>
			</div>
		{/snippet}
	</Async>

	<Async promise={alerts} height={90} loadingText="Preparando la alerta principal…">
		{#snippet children(a: any)}
			{#if a.items?.[0]}
				{@const top = a.items[0]}
				<a class="alert card" href="/alertas" style="--c:{lossColor(top.perdida_pct)}">
					<span class="aic"><Icon name="bell" size={22} /></span>
					<span class="at"><small>Alerta principal · temporada actual</small><b>{top.titulo}</b><span>{top.mensaje}</span></span>
					<span class="go">Ver {a.items.length} alertas →</span>
				</a>
			{/if}
		{/snippet}
	</Async>

	<div class="grid3">
		<div class="card box">
			<h3><Icon name="wave" size={18} /> El Niño hoy</h3>
			<Async promise={enso} height={100}>
				{#snippet children(e: any)}
					<p class="big">{ENSO_LABEL[e.phase] ?? e.phase}{e.intensity ? ` ${INTENSITY[e.intensity] ?? e.intensity}` : ''}</p>
					<p class="muted">{e.message_es}</p>
					<button class="lnk" onclick={() => goto('/el-nino')}>¿Qué significa para mi cacao? →</button>
				{/snippet}
			</Async>
		</div>
		<div class="card box">
			<h3><Icon name="farm" size={18} /> El cacao en 2050</h3>
			<Async promise={zones} height={100}>
				{#snippet children(z: any)}
					{@const c = z.items.reduce((m: any, i: any) => ((m[i.zone_class] = (m[i.zone_class] ?? 0) + 1), m), {})}
					<p class="big">{(c.segura ?? 0) + (c.manejo ?? 0)} <small>cantones aptos</small></p>
					<p class="muted">{c.segura ?? 0} en zona segura y {c.manejo ?? 0} en zona de manejo hacia 2050 (SSP2-4.5); {c.transicion ?? 0} en transición y {c.critica ?? 0} críticos.</p>
					<button class="lnk" onclick={() => { app.mapMode = 'zones'; goto('/'); }}>Ver zonas 2050 en el mapa →</button>
				{/snippet}
			</Async>
		</div>
		<div class="card box">
			<h3><Icon name="bell" size={18} /> Más afectados</h3>
			<Async promise={summary} height={100}>
				{#snippet children(s: any)}
					{#each s.top_areas.slice(0, 5) as t}
						<button class="tl" onclick={() => open(t.area_id, t.name)}><span>{t.name}</span><b>{usd(t.loss_usd)}</b></button>
					{/each}
				{/snippet}
			</Async>
		</div>
	</div>

	<div class="grid2">
		<section class="card box">
			<h3>Pérdida total por escenario</h3>
			<p class="muted">Millones de USD · toca un escenario arriba para verlo en el mapa</p>
			{#if bars}
				<Chart labels={bars.labels} series={[{ name: 'Millones USD', color: '#a99f6a', values: bars.usd, type: 'bar' }, { name: 'Toneladas', color: '#2f7f73', values: bars.t, axis: 'right' }]} unit=" M" unitRight=" t" height={230} />
			{:else}<div class="skeleton" style="min-height:230px"></div>{/if}
		</section>
		<section class="card box">
			<h3>Cantones por nivel de pérdida</h3>
			<p class="muted">Cada barra suma el 100 % de los cantones · toca una para usar ese escenario</p>
			<ClassMix />
		</section>
	</div>

	<section class="card box">
		<h3>Dónde más sube la pérdida frente a un año normal</h3>
		<p class="muted">Por provincia, en puntos de pérdida · toca una para filtrar el mapa</p>
		<Async promise={rising} height={160}>
			{#snippet children(r: any[])}
				{@const max = Math.max(...r.map((x) => x.delta), 1)}
				<div class="rise">
					{#each r as x}
						<button class="ri" onclick={() => { app.province = x.name; goto('/'); }}>
							<span class="n">{x.name}</span>
							<span class="track"><i style="width:{Math.max(2, (x.delta / max) * 100)}%;background:{lossColor(x.loss_pct)}"></i></span>
							<span class="v">+{num(x.delta, 1)} pts <small>→ {pct(x.loss_pct)}</small></span>
						</button>
					{/each}
				</div>
			{/snippet}
		</Async>
	</section>
</div>

<style>
	.pg { max-width: 1180px; margin: 0 auto; padding: 1.6rem 1.4rem 3rem; display: flex; flex-direction: column; gap: 1.1rem; }
	.ph small { font: 600 0.72rem/1 var(--font); text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-2); }
	.ph h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); margin-top: 0.3rem; }
	.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.8rem; }
	.k { display: flex; flex-direction: column; gap: 0.15rem; box-shadow: var(--shadow); }
	.ic, .aic { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent); margin-bottom: 0.4rem; }
	.k .value { font-size: 1.7rem; }
	.k .label { text-transform: none; font-size: 0.85rem; letter-spacing: 0; color: var(--ink); }
	.alert { display: flex; align-items: center; gap: 1rem; text-decoration: none; color: inherit; border-left: 6px solid var(--c); box-shadow: var(--shadow); }
	.alert:hover { border-color: var(--accent); border-left-color: var(--c); }
	.aic { margin: 0; flex-shrink: 0; }
	.at { display: flex; flex-direction: column; gap: 0.15rem; flex: 1; min-width: 0; }
	.at small { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2); }
	.at b { font-family: var(--display); font-size: 1.05rem; color: var(--heading); }
	.at span { color: var(--ink-2); font-size: 0.88rem; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.go { color: var(--accent); font-weight: 700; white-space: nowrap; }
	.grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem; }
	.grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.8rem; }
	.box { display: flex; flex-direction: column; gap: 0.5rem; box-shadow: var(--shadow); }
	.box h3 { display: flex; align-items: center; gap: 0.4rem; font-family: var(--display); font-size: 1.05rem; color: var(--heading); }
	.big { font-family: var(--display); font-size: 1.6rem; font-weight: 700; color: var(--heading); margin: 0; }
	.big small { font-family: var(--font); font-size: 0.85rem; font-weight: 500; color: var(--ink-2); }
	.lnk { border: 0; background: none; padding: 0; color: var(--accent); font-weight: 600; cursor: pointer; text-align: left; margin-top: auto; }
	.tl { display: flex; justify-content: space-between; border: 0; background: none; padding: 0.42rem 0; border-bottom: 1px solid var(--line); cursor: pointer; color: inherit; }
	.tl:last-child { border-bottom: 0; }
	.tl:hover span { color: var(--accent); }
	.rise { display: flex; flex-direction: column; gap: 0.3rem; }
	.ri { display: grid; grid-template-columns: 170px 1fr 150px; gap: 0.7rem; align-items: center; border: 0; background: none; padding: 0.3rem 0.4rem; border-radius: 10px; cursor: pointer; color: inherit; text-align: left; }
	.ri:hover { background: var(--surface-2); }
	.track { height: 12px; background: var(--surface-2); border-radius: 6px; overflow: hidden; }
	.track i { display: block; height: 100%; border-radius: 6px; }
	.ri .v { font-size: 0.85rem; font-weight: 600; }
	.ri small { color: var(--ink-2); font-weight: 400; }
	@media (max-width: 1000px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } .grid3, .grid2 { grid-template-columns: 1fr; } }
	@media (max-width: 640px) { .pg { padding: 1rem 0.9rem 2rem; } .ri { grid-template-columns: 110px 1fr; } .ri .v { grid-column: 1 / -1; } .alert { flex-wrap: wrap; } }
</style>
