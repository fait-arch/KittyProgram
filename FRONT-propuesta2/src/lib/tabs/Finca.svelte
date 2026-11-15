<script lang="ts">
	// Mi finca: hectáreas dibujadas × rendimiento × % de pérdida del cantón = lo que arriesga el lote.
	// Clima del punto central con NASA POWER (pestaña Punto). Las fincas se guardan solo en este navegador.
	import { untrack } from 'svelte';
	import { api } from '#lib/api';
	import { app, type Finca } from '#lib/state.svelte';
	import { num, pct, usd, lossColor, lossLabel } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import Punto from './Punto.svelte';

	let { f }: { f: Finca } = $props();
	let yieldT = $state(0.6);      // t de grano seco por ha y año (promedio ESPAC Ecuador ≈ 0,6)
	let price = $state(5600);      // USD por tonelada
	let name = $state(untrack(() => f.name ?? ''));
	let saved = $state(false);

	const detail = $derived(f.cantonId ? api.detail(f.cantonId, app.scenario, app.crop) : null);
	const KEY = 'cr-fincas';
	const list = (): Finca[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? '[]'); } catch { return []; } };
	let fincas = $state<Finca[]>(list());
	function save() {
		const all = list().filter((x) => x.name !== (name || 'Mi finca'));
		all.unshift({ ...f, name: name || 'Mi finca' });
		try { localStorage.setItem(KEY, JSON.stringify(all.slice(0, 20))); } catch { /* */ }
		fincas = all; saved = true; setTimeout(() => (saved = false), 2000);
	}
	function remove(n: string | undefined) {
		const all = list().filter((x) => x.name !== n);
		try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* */ }
		fincas = all;
	}
	const haTxt = (h: number) => (h < 10 ? h.toFixed(2) : h.toFixed(1));
</script>

<div class="hero">
	<div class="kpi"><div class="label">Superficie dibujada</div><div class="value">{haTxt(f.ha)} ha</div>
		<div class="sub">{f.cantonName ? `En ${f.cantonName}` : 'Fuera de los cantones de la base'}</div></div>
	{#if f.cantonId}<button class="btn sm" onclick={() => app.select(f.cantonId!, f.cantonName)}>Ver cantón →</button>{/if}
</div>

{#if detail}
	<Async promise={detail} height={140}>
		{#snippet children(d: any)}
			{@const L = d.loss}
			{#if L}
				{@const t = (f.ha * yieldT * L.loss_pct) / 100}
				<div class="res card" style="--c:{lossColor(L.loss_pct)}">
					<div class="spread"><b>Lo que arriesga tu finca</b><span class="pill">{lossLabel(L.loss_pct)} · {pct(L.loss_pct)}</span></div>
					<div class="grid2">
						<div class="kpi"><div class="label">Grano perdido</div><div class="value">{num(t * 1000)} kg</div><div class="sub">rango {num((f.ha * yieldT * L.loss_pct_low) / 100 * 1000)}–{num((f.ha * yieldT * L.loss_pct_high) / 100 * 1000)} kg</div></div>
						<div class="kpi"><div class="label">Dinero</div><div class="value">{usd(t * price, true)}</div><div class="sub">a {usd(price, true)} por tonelada</div></div>
					</div>
					<div class="grid2 inputs">
						<label>Rendimiento (t/ha)<input type="number" min="0.1" max="3" step="0.05" bind:value={yieldT} /></label>
						<label>Precio (USD/t)<input type="number" min="500" max="15000" step="50" bind:value={price} /></label>
					</div>
					<small class="muted">Usa la pérdida estimada del cantón ({d.area?.name ?? f.cantonName}) para el escenario elegido. Ajusta el rendimiento a tu finca.</small>
				</div>
			{:else}
				<p class="muted">El modelo no tiene estimación para este cantón todavía.</p>
			{/if}
		{/snippet}
	</Async>
{/if}

<Section title="Guardar esta finca" hint="Solo en este navegador: no se envía a ningún servidor">
	<div class="row">
		<input type="text" placeholder="Nombre (p. ej. Lote del río)" bind:value={name} maxlength="40" />
		<button class="btn sm primary" onclick={save}><Icon name={saved ? 'check' : 'download'} size={15} />{saved ? 'Guardada' : 'Guardar'}</button>
		<button class="btn sm" onclick={() => app.startFinca()}><Icon name="farm" size={15} /> Dibujar otra</button>
	</div>
	{#if fincas.length}
		<ul class="saved">
			{#each fincas as x}
				<li>
					<button class="lnk" onclick={() => (app.finca = x)}>{x.name} <small>{haTxt(x.ha)} ha · {x.cantonName || '—'}</small></button>
					<button class="del" onclick={() => remove(x.name)} aria-label="Borrar {x.name}"><Icon name="trash" size={15} /></button>
				</li>
			{/each}
		</ul>
	{/if}
</Section>

<Section title="Clima de tu finca" hint="NASA POWER en el punto central del lote">
	<Punto lat={+f.center[1].toFixed(4)} lon={+f.center[0].toFixed(4)} />
</Section>

<style>
	.hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
	.res { display: flex; flex-direction: column; gap: 0.7rem; border-left: 5px solid var(--c); }
	.inputs label { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.78rem; color: var(--ink-2); }
	.inputs input { color: var(--ink); }
	.row input { flex: 1; }
	.saved { list-style: none; margin: 0.5rem 0 0; padding: 0; display: flex; flex-direction: column; gap: 0.2rem; }
	.saved li { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--line); }
	.lnk { border: 0; background: none; text-align: left; padding: 0.4rem 0; cursor: pointer; display: flex; flex-direction: column; color: inherit; }
	.lnk:hover { color: var(--accent); }
	.del { border: 0; background: none; color: var(--ink-2); cursor: pointer; padding: 0.3rem; border-radius: 8px; }
	.del:hover { color: var(--bad); background: var(--surface-2); }
</style>
