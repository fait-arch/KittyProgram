<script lang="ts">
	import type { Snippet } from 'svelte';
	let { title, hint = '', aside, children }: { title: string; hint?: string; aside?: Snippet; children: Snippet } = $props();
</script>

<section>
	<div class="head">
		<div>
			<h3>{title}</h3>
			{#if hint}<small>{hint}</small>{/if}
		</div>
		{#if aside}{@render aside()}{/if}
	</div>
	{@render children()}
</section>

<style>
	section { display: flex; flex-direction: column; gap: 0.7rem; }
	.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; }
	small { display: block; margin-top: 0.1rem; }
</style>
