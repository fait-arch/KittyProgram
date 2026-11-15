<script lang="ts">
	import '../app.css';
	import { app } from '#lib/state.svelte';
	import TopBar from '#lib/components/TopBar.svelte';
	import Nav from '#lib/components/Nav.svelte';
	import Drawer from '#lib/components/Drawer.svelte';
	import EnsoModal from '#lib/components/EnsoModal.svelte';
	import MethodModal from '#lib/components/MethodModal.svelte';
	import AlertsModal from '#lib/components/AlertsModal.svelte';
	import ExportModal from '#lib/components/ExportModal.svelte';
	import ShareModal from '#lib/components/ShareModal.svelte';
	import TermsModal from '#lib/components/TermsModal.svelte';
	let { children } = $props();
</script>

<div class="app">
	<TopBar />
	<div class="shell">
		<Nav />
		<main>{@render children()}</main>
	</div>
</div>

{#if app.modal === 'enso'}<EnsoModal />{/if}
{#if app.modal === 'method'}<MethodModal />{/if}
{#if app.modal === 'alerts'}<AlertsModal />{/if}
{#if app.modal === 'export'}<ExportModal />{/if}
{#if app.modal === 'share'}<ShareModal />{/if}
{#if app.modal === 'terms'}<TermsModal />{/if}
<Drawer />

<style>
	.app { height: 100dvh; display: flex; flex-direction: column; }
	.shell { flex: 1; min-height: 0; display: flex; align-items: stretch; flex-wrap: nowrap; }
	main { position: relative; flex: 1; min-width: 0; min-height: 0; overflow: auto; background: var(--bg); }
	@media (max-width: 900px) { .shell { flex-direction: column-reverse; } }
	@media print { .app { height: auto; } main { overflow: visible; } }
</style>
