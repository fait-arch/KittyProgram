<script lang="ts">
	import { app } from '#lib/state.svelte';
	import Resumen from '#lib/tabs/Resumen.svelte';
	import Clima from '#lib/tabs/Clima.svelte';
	import Riesgo from '#lib/tabs/Riesgo.svelte';
	import Estrategias from '#lib/tabs/Estrategias.svelte';
	import Simular from '#lib/tabs/Simular.svelte';
	import Comparar from '#lib/tabs/Comparar.svelte';
	import IA from '#lib/tabs/IA.svelte';
	import Campo from '#lib/tabs/Campo.svelte';
	import Punto from '#lib/tabs/Punto.svelte';

	const TABS = [
		{ id: 'resumen', label: 'Resumen', C: Resumen },
		{ id: 'estrategias', label: 'Qué hacer', C: Estrategias },
		{ id: 'ia', label: 'Asistente IA', C: IA },
		{ id: 'riesgo', label: 'Enfermedades', C: Riesgo },
		{ id: 'clima', label: 'Clima', C: Clima },
		{ id: 'comparar', label: 'Escenarios', C: Comparar },
		{ id: 'simular', label: 'Simular', C: Simular },
		{ id: 'campo', label: 'Campo', C: Campo }
	];
	const Current = $derived(TABS.find((t) => t.id === app.tab)?.C ?? Resumen);
</script>

{#if app.selectedId || app.point}
	<aside class="panel">
		<header>
			<div>
				<small>{app.point ? 'Punto libre · NASA POWER' : 'Cantón'}</small>
				<h2>{app.point ? `${app.point.lat}, ${app.point.lon}` : app.selectedName || '…'}</h2>
			</div>
			<button class="btn sm" onclick={() => app.clear()} aria-label="Cerrar panel">✕</button>
		</header>
		{#if app.selectedId}
			<nav>
				{#each TABS as t}
					<button class:on={app.tab === t.id} onclick={() => (app.tab = t.id)}>{t.label}</button>
				{/each}
			</nav>
			<div class="body">
				{#key app.selectedId}<Current id={app.selectedId} />{/key}
			</div>
		{:else if app.point}
			<div class="body"><Punto lat={app.point.lat} lon={app.point.lon} /></div>
		{/if}
	</aside>
{/if}

<style>
	.panel {
		position: absolute; top: 20px; right: 20px; bottom: 20px; z-index: 4; width: 450px;
		background: var(--surface); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow);
		display: flex; flex-direction: column; overflow: hidden; animation: slide 0.25s ease-out;
	}
	@keyframes slide { from { transform: translateX(16px); opacity: 0; } }
	header { display: flex; justify-content: space-between; align-items: flex-start; padding: 1.1rem 1.3rem 0.8rem; background: var(--accent-soft); }
	header small { color: var(--accent); }
	header small { text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.7rem; }
	nav { display: flex; gap: 0.2rem; padding: 0 1rem; border-bottom: 1px solid var(--line); background: var(--accent-soft); overflow-x: auto; scrollbar-width: none; flex-shrink: 0; }
	nav button { border: 0; background: none; padding: 0.65rem 0.5rem; font-size: 0.9rem; cursor: pointer; color: var(--ink-2); font-weight: 500; border-bottom: 2px solid transparent; white-space: nowrap; }
	nav button.on { color: var(--heading); font-weight: 600; border-bottom: 3px solid var(--accent); }
	nav button:hover { color: var(--accent); }
	.body { padding: 1.25rem 1.3rem 1.6rem; overflow: auto; flex: 1; display: flex; flex-direction: column; gap: 1.6rem; }
	@media (max-width: 900px) {
		.panel { top: auto; left: 0; right: 0; bottom: 0; width: auto; height: 68vh; border-radius: 18px 18px 0 0; animation-name: up; z-index: 6; }
		@keyframes up { from { transform: translateY(24px); opacity: 0; } }
	}
</style>
