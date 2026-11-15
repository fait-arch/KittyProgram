<script lang="ts">
	let { page = false }: { page?: boolean } = $props();
	// GET /alerts: avisos por provincia en lenguaje natural (los redacta la IA; si no, una plantilla con los mismos datos)
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { lossColor, lossLabel, LOSS_ON, lossLevel, num, pct, usd } from '#lib/fmt';
	import Modal from './Modal.svelte';
	import Async from './Async.svelte';
	import Segmented from './Segmented.svelte';
	import Icon from './Icon.svelte';
	import { goto } from '$app/navigation';

	const OPTS = [
		{ id: 'actual', label: 'Hoy' },
		{ id: 'nino_extremo', label: 'Niño extremo' },
		{ id: 'nino', label: 'Año Niño' },
		{ id: 'normal', label: 'Normal' }
	];
	let scenario = $state(OPTS.some((o) => o.id === app.scenario) ? app.scenario : 'actual');
	const data = $derived(api.alerts(scenario, app.province || undefined, app.crop));
	let open = $state<string | null>(null);

	const wa = (a: any) =>
		`https://wa.me/593964213841?text=${encodeURIComponent(`Hola, vi la alerta de CacaoResiliente para ${a.provincia}: "${a.titulo}". Quisiera asesoría.`)}`;
	function verEnMapa(a: any) {
		app.province = a.provincia;
		app.scenario = scenario;
		app.mapMode = 'loss';
		app.modal = null;
		if (page) goto('/');
	}
</script>

<Modal title="Alertas" wide {page} kicker="Avisos por provincia" onclose={() => (app.modal = null)}>
	<div class="spread top">
		<p class="muted">Avisos por provincia para el escenario elegido{app.province ? ` · ${app.province}` : ''}. Las cifras las calcula el modelo; la IA solo las pone en palabras.</p>
		<Segmented options={OPTS} bind:value={scenario} size="sm" />
	</div>

	<Async promise={data} height={220} loadingText="La IA está redactando las alertas (puede tardar hasta un minuto)…">
		{#snippet children(r: any)}
			{#if r.resumen}
				<div class="sum card">
					<span class="badge">{r.generated_by === 'ia' ? `Redactado por IA${r.model ? ` · ${r.model}` : ''}` : 'Texto automático'}</span>
					<p>{r.resumen}</p>
				</div>
			{/if}
			{#if !r.items?.length}
				<p class="muted">Sin alertas para este escenario.</p>
			{/if}
			<div class="list">
				{#each r.items as a (a.area_id)}
					{@const lv = Math.max(0, lossLevel(a.perdida_pct))}
					<article class="al card" style="--c:{lossColor(a.perdida_pct)}; --on:{LOSS_ON[lv]}">
						<header>
							<span class="lvl">{lossLabel(a.perdida_pct)} · {pct(a.perdida_pct)}</span>
							<small>{a.provincia}</small>
						</header>
						<h3>{a.titulo}</h3>
						<p>{a.mensaje}</p>
						{#if a.accion}<p class="acc"><b>Qué hacer:</b> {a.accion}{#if a.cuando} <span class="muted">· {a.cuando}</span>{/if}</p>{/if}
						<div class="row facts">
							{#if a.perdida_t != null}<span class="pill">{num(a.perdida_t)} t</span>{/if}
							{#if a.perdida_usd != null}<span class="pill">{usd(a.perdida_usd)}</span>{/if}
							{#if a.vs_normal_pts != null}<span class="pill">{a.vs_normal_pts > 0 ? '+' : ''}{num(a.vs_normal_pts, 1)} pts vs. normal</span>{/if}
							{#if a.extrapolado}<span class="pill">Extrapolación</span>{/if}
						</div>
						<details open={open === a.area_id} ontoggle={(e) => (open = e.currentTarget.open ? a.area_id : null)}>
							<summary>Ver el cálculo</summary>
							<ul>
								<li>Rango probable: {pct(a.rango_pct?.[0])} – {pct(a.rango_pct?.[1])}</li>
								{#if a.factor_principal}<li>Factor que más pesa: {a.factor_principal}</li>{/if}
								{#if a.prob_perder_mas_20 != null}<li>Probabilidad de perder más del 20 %: {Math.round(a.prob_perder_mas_20 * 100)} %</li>{/if}
								{#if a.cantones?.length}<li>Cantones: {a.cantones.join(', ')}</li>{/if}
							</ul>
						</details>
						<div class="row acts">
							<button class="btn sm" onclick={() => verEnMapa(a)}><Icon name="map" size={16} /> Ver en el mapa</button>
							<a class="btn sm primary" href={wa(a)} target="_blank" rel="noopener noreferrer"><Icon name="chat" size={16} /> Pedir asesoría</a>
						</div>
					</article>
				{/each}
			</div>
			{#if r.disclaimer}<p class="disclaimer">{r.disclaimer}</p>{/if}
		{/snippet}
	</Async>
</Modal>

<style>
	.top { align-items: flex-start; flex-wrap: wrap; }
	.top p { flex: 1; min-width: 220px; margin: 0; }
	.sum { background: var(--accent-soft); border: 0; display: flex; flex-direction: column; gap: 0.4rem; }
	.badge { align-self: flex-start; font-size: 0.72rem; font-weight: 600; padding: 0.15rem 0.6rem; border-radius: 999px; background: var(--surface); color: var(--accent); }
	.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.8rem; }
	.al { display: flex; flex-direction: column; gap: 0.5rem; border-left: 5px solid var(--c); }
	.al header { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
	.lvl { background: var(--c); color: var(--on); font-size: 0.75rem; font-weight: 700; padding: 0.15rem 0.6rem; border-radius: 999px; }
	.al h3 { font-family: var(--display); font-size: 1.05rem; color: var(--heading); }
	.al p { margin: 0; }
	.acc { font-size: 0.9rem; }
	.facts { gap: 0.35rem; }
	details { font-size: 0.85rem; color: var(--ink-2); }
	summary { cursor: pointer; color: var(--accent); font-weight: 500; }
	details ul { margin: 0.4rem 0 0; padding-left: 1.1rem; }
	.acts { margin-top: auto; }
	.acts a { text-decoration: none; }
</style>
