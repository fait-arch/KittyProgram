<script lang="ts">
	import { onMount } from 'svelte';
	import { app } from '#lib/state.svelte';
	import MapView from '#lib/components/MapView.svelte';
	import Overview from '#lib/components/Overview.svelte';
	import AreaPanel from '#lib/components/AreaPanel.svelte';

	// Enlaces compartibles: el estado entra desde la URL y se refleja en ella (sin recargar)
	let ready = $state(false);
	onMount(() => { app.fromUrl(); ready = true; });
	$effect(() => {
		const u = app.url;
		if (ready) history.replaceState(history.state, '', u);
	});
</script>

<svelte:head><title>CacaoResiliente · Mapa</title></svelte:head>

<div class="map">
	<MapView />
	<Overview />
	<AreaPanel />
</div>

<style>
	.map { position: absolute; inset: 0; overflow: hidden; }
</style>
