<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import { errMsg } from '#lib/fmt';
	// Envuelve una promesa: skeleton mientras carga, error legible si falla.
	let { promise, children, height = 80, loadingText = '' }: { promise: Promise<T> | null; children: Snippet<[T]>; height?: number; loadingText?: string } = $props();
</script>

{#if promise}
	{#await promise}
		<div class="skeleton" style="min-height:{height}px">{#if loadingText}<span class="lt">{loadingText}</span>{/if}</div>
	{:then data}
		{@render children(data)}
	{:catch e}
		<p class="err">{errMsg(e)}</p>
	{/await}
{/if}

<style>
	.skeleton { display: grid; place-items: center; }
	.lt { font-size: 0.85rem; color: var(--ink-2); }
</style>
