<script lang="ts">
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { ENSO_LABEL, INTENSITY } from '#lib/fmt';
	import Segmented from './Segmented.svelte';

	let scenarios = $state<any[]>([]);
	let crops = $state<any[]>([]);
	let provinces = $state<any[]>([]);
	let enso = $state<any>(null);
	let health = $state<any>(null);
	let menu = $state(false);

	$effect(() => { api.scenarios(app.crop).then((s) => (scenarios = s)).catch(() => {}); void app.refresh; });
	$effect(() => {
		api.crops().then((c) => (crops = c)).catch(() => {});
		api.areas({ kind: 'province' }).then((p) => (provinces = p)).catch(() => {});
		api.ensoCurrent().then((e) => (enso = e)).catch(() => {});
	});
	$effect(() => {
		void app.refresh;
		const tick = () => api.health().then((h) => (health = h)).catch(() => (health = { status: 'down' }));
		tick();
		const t = setInterval(tick, 60000);
		return () => clearInterval(t);
	});

	const SHORT: Record<string, string> = { normal: 'Normal', nino: 'Niño', nina: 'Niña', actual: 'Hoy', ssp245_2050: '2050 · mod.', ssp585_2050: '2050 · alto' };
	const opts = $derived(scenarios.map((s) => ({ id: s.id, label: SHORT[s.id] ?? s.name_es, disabled: !s.available, hint: `${s.name_es} — ${s.description ?? ''}${s.available ? '' : ' (sin predicción aún)'}` })));
	const statusColor = $derived(health?.status === 'ok' ? 'var(--good)' : health?.status === 'degraded' ? 'var(--warn)' : 'var(--bad)');
	const open = (m: typeof app.modal) => { app.modal = m; menu = false; };
</script>

<header class="bar">
	<div class="brand">
		<svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true"><ellipse cx="16" cy="16" rx="9" ry="14" fill="#5a3a22" /><path d="M16 3v26M10 8c3 3 3 13 0 16M22 8c-3 3-3 13 0 16" stroke="#9cc58a" stroke-width="1.6" fill="none" /></svg>
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
		<button class="btn icon" onclick={() => app.toggleTheme()} aria-label={app.theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'} title={app.theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}>
			{#if app.theme === 'dark'}
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
			{:else}
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
			{/if}
		</button>
		<div class="menuwrap">
			<button class="btn icon" onclick={() => (menu = !menu)} aria-label="Menú" aria-expanded={menu}>
				<span class="hd" style="background:{statusColor}"></span>☰
			</button>
			{#if menu}
				<div class="menu card">
					<label>Cultivo
						<select bind:value={app.crop}>{#each crops as c}<option value={c.id}>{c.name_es}</option>{/each}</select>
					</label>
					<label>Provincia
						<select bind:value={app.province}>
							<option value="">Todo el país</option>
							{#each provinces as p}<option value={p.name}>{p.name}</option>{/each}
						</select>
					</label>
					<hr />
					<button onclick={() => open('enso')}>🌊 El Niño: historia y eventos</button>
					<button onclick={() => open('method')}>📚 Metodología y fuentes</button>
					<button onclick={() => open('login')}>{app.token ? `👤 ${app.userEmail || 'Sesión activa'}` : '👤 Iniciar sesión (técnicos)'}</button>
					<button onclick={() => open('admin')}>⚙ Estado y administración</button>
					<hr />
					<small class="st"><span class="hd" style="background:{statusColor}"></span> API {health?.status ?? '…'} · datos {health?.data_source ?? '?'}</small>
				</div>
			{/if}
		</div>
	</div>
</header>
{#if menu}<div class="scrim" onclick={() => (menu = false)} role="presentation"></div>{/if}

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
	.enso.nino .dot { background: #8b5e3c; box-shadow: 0 0 0 4px rgb(139 94 60 / 0.2); }
	.enso.nina .dot { background: #4d7484; box-shadow: 0 0 0 4px rgb(77 116 132 / 0.2); }
	.menuwrap { position: relative; }
	.icon { position: relative; width: 38px; height: 38px; justify-content: center; padding: 0; background: rgb(255 255 255 / 0.08); border-color: rgb(255 255 255 / 0.18); color: #fff; }
	.icon:hover { background: rgb(255 255 255 / 0.16); color: #fff; border-color: rgb(255 255 255 / 0.3); }
	.hd { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
	.icon .hd { position: absolute; top: 4px; right: 4px; }
	.menu { color: var(--ink); position: absolute; right: 0; top: calc(100% + 8px); width: 270px; display: flex; flex-direction: column; gap: 0.4rem; box-shadow: var(--shadow); z-index: 12; padding: 0.9rem; }
	.menu label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.78rem; color: var(--ink-2); }
	.menu select { color: var(--ink); }
	.menu button { text-align: left; border: 0; background: none; padding: 0.5rem 0.4rem; border-radius: 8px; cursor: pointer; }
	.menu button:hover { background: var(--surface-2); }
	.menu hr { border: 0; border-top: 1px solid var(--line); margin: 0.3rem 0; width: 100%; }
	.st { display: flex; align-items: center; gap: 0.4rem; }
	.scrim { position: fixed; inset: 0; z-index: 9; }
	@media (max-width: 900px) {
		.bar { grid-template-columns: 1fr auto; grid-template-rows: auto auto; padding: 0.6rem 0.9rem; gap: 0.5rem; }
		.center { grid-column: 1 / -1; grid-row: 2; justify-content: flex-start; }
		.brand small, .enso small { display: none; }
		h1 { font-size: 1.05rem; }
		.brand svg { width: 22px; }
	}
</style>
