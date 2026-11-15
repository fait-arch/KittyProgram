<script lang="ts">
	// Menú de secciones: riel izquierdo plegable (escritorio) y barra inferior (móvil).
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { app } from '#lib/state.svelte';
	import Icon from './Icon.svelte';

	const ITEMS = [
		{ href: '/', label: 'Mapa', icon: 'map' },
		{ href: '/panel', label: 'Panel', icon: 'dash' },
		{ href: '/alertas', label: 'Alertas', icon: 'bell' },
		{ href: '/comparar', label: 'Comparar', icon: 'compare' },
		{ href: '/finca', label: 'Mi finca', icon: 'farm' },
		{ href: '/el-nino', label: 'El Niño', icon: 'wave' },
		{ href: '/metodologia', label: 'Método', icon: 'book' }
	];
	const MOBILE = ITEMS.slice(0, 5);

	function load(k: string) { try { return localStorage.getItem(k); } catch { return null; } }
	let folded = $state(load('cr_nav') === '1');
	function toggle() { folded = !folded; try { localStorage.setItem('cr_nav', folded ? '1' : '0'); } catch { /* */ } }
	const active = (href: string) => (href === '/' ? page.url.pathname === '/' && !app.fincaMode : href === '/finca' ? app.fincaMode || page.url.pathname === '/finca' : page.url.pathname.startsWith(href));

	function go(e: MouseEvent, href: string) {
		if (href !== '/finca') { if (app.fincaMode && href === '/') app.fincaMode = false; return; }
		e.preventDefault();
		app.startFinca();
		if (page.url.pathname !== '/') goto('/');
	}
</script>

<nav class="rail" class:folded aria-label="Secciones">
	{#each ITEMS as it}
		<a href={it.href} class:on={active(it.href)} onclick={(e) => go(e, it.href)} title={it.label} aria-current={active(it.href) ? 'page' : undefined}>
			<span class="pill"><Icon name={it.icon} size={21} /></span>
			{#if !folded}<span class="lb">{it.label}</span>{/if}
		</a>
	{/each}
	<button class="fold" onclick={toggle} aria-label={folded ? 'Mostrar nombres del menú' : 'Plegar menú'} title={folded ? 'Mostrar nombres' : 'Plegar menú'}>
		<Icon name={folded ? 'chevR' : 'chevL'} size={18} />
	</button>
</nav>

<nav class="bottom" aria-label="Secciones">
	{#each MOBILE as it}
		<a href={it.href} class:on={active(it.href)} onclick={(e) => go(e, it.href)} aria-current={active(it.href) ? 'page' : undefined}>
			<span class="pill"><Icon name={it.icon} size={21} /></span>
			<span class="lb">{it.label}</span>
		</a>
	{/each}
</nav>

<style>
	.rail { width: 84px; flex-shrink: 0; background: var(--surface); border-right: 1px solid var(--line); display: flex; flex-direction: column; align-items: stretch; gap: 0.25rem; padding: 0.7rem 0.4rem; overflow-y: auto; z-index: 8; }
	.rail.folded { width: 62px; }
	a { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; padding: 0.25rem 0; text-decoration: none; color: var(--ink-2); font-size: 0.74rem; font-weight: 600; border-radius: 12px; }
	.pill { width: 52px; height: 32px; border-radius: 999px; display: grid; place-items: center; transition: background 0.2s, color 0.2s; }
	a:hover .pill { background: var(--surface-2); color: var(--ink); }
	a.on { color: var(--heading); }
	a.on .pill { background: var(--accent-soft); color: var(--accent); }
	:global([data-theme='dark']) a.on .pill { background: #3d5a43; color: #d8efe3; }
	.fold { margin-top: auto; align-self: center; width: 36px; height: 36px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink-2); display: grid; place-items: center; cursor: pointer; }
	.fold:hover { color: var(--accent); border-color: var(--accent); }
	.bottom { display: none; }
	@media (max-width: 900px) {
		.rail { display: none; }
		.bottom { display: flex; justify-content: space-around; background: var(--surface); border-top: 1px solid var(--line); padding: 0.35rem 0.2rem calc(0.35rem + env(safe-area-inset-bottom)); z-index: 8; }
		.bottom a { flex: 1; }
	}
	@media print { .rail, .bottom { display: none; } }
</style>
