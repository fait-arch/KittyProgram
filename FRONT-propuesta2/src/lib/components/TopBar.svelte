<script lang="ts">
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { ENSO_LABEL, INTENSITY } from '#lib/fmt';
	import Segmented from './Segmented.svelte';
	import Icon from './Icon.svelte';

	let scenarios = $state<any[]>([]);
	let enso = $state<any>(null);
	let health = $state<any>(null);

	$effect(() => { api.scenarios(app.crop).then((s) => (scenarios = s)).catch(() => {}); void app.refresh; });
	$effect(() => {
		api.ensoCurrent().then((e) => (enso = e)).catch(() => {});
	});
	$effect(() => {
		void app.refresh;
		const tick = () => api.health().then((h) => (health = h, app.health = h)).catch(() => (health = { status: 'down' }, app.health = health));
		tick();
		const t = setInterval(tick, 60000);
		return () => clearInterval(t);
	});

	const SHORT: Record<string, string> = { normal: 'Normal', nino: 'Niño', nina: 'Niña', nino_extremo: 'Niño extremo', actual: 'Hoy', ssp245_2050: '2050 · mod.', ssp585_2050: '2050 · alto' };
	// WhatsApp de asesoría (mismo número que FRONT). Si hay un cantón abierto, el mensaje ya lo menciona.
	const WA = '593964213841';
	const waHref = $derived(`https://wa.me/${WA}?text=${encodeURIComponent(app.selectedName
		? `Hola, consulté CacaoResiliente sobre ${app.selectedName} (escenario ${SHORT[app.scenario] ?? app.scenario}). Quisiera asesoría.`
		: 'Hola, quisiera asesoría sobre mi cultivo de cacao (CacaoResiliente).')}`);
	const opts = $derived(scenarios.map((s) => ({ id: s.id, label: SHORT[s.id] ?? s.name_es, disabled: !s.available, hint: `${s.name_es} — ${s.description ?? ''}${s.available ? '' : ' (sin predicción aún)'}` })));
	const statusColor = $derived(health?.status === 'ok' ? 'var(--good)' : health?.status === 'degraded' ? 'var(--warn)' : 'var(--bad)');
	const open = (m: typeof app.modal) => { app.modal = m; app.drawer = false; };
</script>

<header class="bar">
	<div class="brand">
		<img src="/favicon.svg" width="36" height="36" alt="" class="logo" />
		<div>
			<h1>CacaoResiliente</h1>
			<small>Pérdidas de cacao por El Niño · hoy y 2050</small>
		</div>
	</div>

	<div class="center">
		<Segmented options={opts} bind:value={app.scenario} dark />
	</div>

	<div class="right">
		{#if enso}
			<button class="enso {enso.phase}" onclick={() => open('enso')} title={enso.message_es}>
				<span class="dot"></span>
				{ENSO_LABEL[enso.phase] ?? enso.phase}{enso.intensity ? ` ${INTENSITY[enso.intensity] ?? enso.intensity}` : ''}
				<small>ONI {enso.oni?.value?.toFixed(1)}</small>
			</button>
		{/if}
		<a class="wa" href={waHref} target="_blank" rel="noopener noreferrer" title="Asesoría por WhatsApp">
			<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path fill="currentColor" d="M20 4H4a2 2 0 0 0-2 2v15l4-4h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM7 9h10v2H7zm6 5H7v-2h6z"/></svg>
			<span>Asesoría</span>
		</a>
		<button class="btn icon" onclick={() => app.toggleTheme()} aria-label={app.theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'} title={app.theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}>
			{#if app.theme === 'dark'}
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
			{:else}
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
			{/if}
		</button>
		<button class="btn icon" onclick={() => (app.drawer = !app.drawer)} aria-label="Menú" aria-expanded={app.drawer}>
			<span class="hd" style="background:{statusColor}"></span><Icon name="menu" size={18} />
		</button>
	</div>
</header>

<style>
	.bar {
		position: relative; z-index: 10; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 1rem;
		padding: 0.75rem 1.25rem; background: var(--bar); color: #fff; transition: background 0.25s;
	}
	.brand { display: flex; gap: 0.65rem; align-items: center; min-width: 0; }
	h1 { font-size: 1.2rem; color: #fff; }
	.brand small { font-size: 0.75rem; color: rgb(255 255 255 / 0.7); }
	.center { display: flex; justify-content: center; min-width: 0; }
	.right { display: flex; justify-content: flex-end; align-items: center; gap: 0.6rem; }
	.enso { display: inline-flex; align-items: center; gap: 0.45rem; border: 1px solid rgb(255 255 255 / 0.18); background: rgb(255 255 255 / 0.08); color: #fff; border-radius: 999px; padding: 0.35rem 0.8rem; cursor: pointer; font-weight: 600; white-space: nowrap; }
	.enso small { font-weight: 400; color: rgb(255 255 255 / 0.7); }
	.enso:hover { background: rgb(255 255 255 / 0.16); }
	.enso .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ink-2); }
	.enso.nino .dot { background: #d9b04f; box-shadow: 0 0 0 4px rgb(217 176 79 / 0.25); }
	.enso.nina .dot { background: #96c9b2; box-shadow: 0 0 0 4px rgb(150 201 178 / 0.25); }
	.logo { border-radius: 10px; flex-shrink: 0; }
	.wa { display: inline-flex; align-items: center; gap: 0.4rem; height: 38px; padding: 0 0.85rem; border-radius: 999px; border: 1px solid rgb(255 255 255 / 0.18);
		background: rgb(255 255 255 / 0.08); color: #fff; text-decoration: none; font-weight: 600; white-space: nowrap; }
	.wa svg { color: #96c9b2; }
	.wa:hover { background: rgb(255 255 255 / 0.16); }
	.icon { position: relative; width: 38px; height: 38px; justify-content: center; padding: 0; background: rgb(255 255 255 / 0.08); border-color: rgb(255 255 255 / 0.18); color: #fff; }
	.icon:hover { background: rgb(255 255 255 / 0.16); color: #fff; border-color: rgb(255 255 255 / 0.3); }
	.hd { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
	.icon .hd { position: absolute; top: 4px; right: 4px; }
	@media (max-width: 1280px) {
		.bar { grid-template-columns: auto 1fr; grid-template-rows: auto auto; row-gap: 0.55rem; }
		.center { grid-column: 1 / -1; grid-row: 2; justify-content: center; }
		.right { grid-column: 2; grid-row: 1; }
	}
	@media (max-width: 900px) {
		.bar { grid-template-columns: 1fr auto; grid-template-rows: auto auto; padding: 0.6rem 0.9rem; gap: 0.5rem; }
		.center { grid-column: 1 / -1; grid-row: 2; justify-content: flex-start; }
		.brand small, .enso small, .wa span { display: none; }
		.wa { width: 38px; padding: 0; justify-content: center; }
		h1 { font-size: 1.05rem; }
		.logo { width: 30px; height: 30px; }
	}
</style>
