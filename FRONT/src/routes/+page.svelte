<script lang="ts">
	import { app } from '#lib/state.svelte';
	import TopBar from '#lib/components/TopBar.svelte';
	import MapView from '#lib/components/MapView.svelte';
	import Overview from '#lib/components/Overview.svelte';
	import AreaPanel from '#lib/components/AreaPanel.svelte';
	import EnsoModal from '#lib/components/EnsoModal.svelte';
	import MethodModal from '#lib/components/MethodModal.svelte';
	import AdminModal from '#lib/components/AdminModal.svelte';
	import LoginModal from '#lib/components/LoginModal.svelte';
</script>

<svelte:head><title>CacaoResiliente</title></svelte:head>

<div class="app">
	<TopBar />
	<main>
		<MapView />
		<Overview />
		<AreaPanel />
	</main>
</div>

{#if app.modal === 'enso'}<EnsoModal />{/if}
{#if app.modal === 'method'}<MethodModal />{/if}
{#if app.modal === 'admin'}<AdminModal />{/if}
{#if app.modal === 'login'}<LoginModal />{/if}

<style>
	.app { height: 100dvh; display: flex; flex-direction: column; }
	main { position: relative; flex: 1; min-height: 0; overflow: hidden; }
</style>
