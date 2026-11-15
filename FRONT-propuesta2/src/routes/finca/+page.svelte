<script lang="ts">
	// Mi finca se dibuja sobre el mapa: esta ruta solo activa el modo dibujo y vuelve al mapa
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { app } from '#lib/state.svelte';
	onMount(() => { app.startFinca(); goto('/', { replaceState: true }); });
</script>
