<script lang="ts">
	type Opt = { id: string; label: string; disabled?: boolean; hint?: string };
	let { options, value = $bindable(), size = 'md', dark = false }: { options: Opt[]; value: string; size?: 'sm' | 'md'; dark?: boolean } = $props();
</script>

<div class="seg {size}" class:dark role="tablist">
	{#each options as o}
		<button role="tab" aria-selected={value === o.id} class:on={value === o.id} disabled={o.disabled} title={o.hint} onclick={() => (value = o.id)}>{o.label}</button>
	{/each}
</div>

<style>
	.seg { display: inline-flex; background: var(--surface-2); padding: 3px; border-radius: 999px; gap: 2px; max-width: 100%; overflow-x: auto; scrollbar-width: none; }
	button { border: 0; background: transparent; padding: 0.4rem 0.85rem; border-radius: 999px; cursor: pointer; font-weight: 500; color: var(--ink-2); white-space: nowrap; transition: background 0.2s, color 0.2s; }
	.sm button { padding: 0.25rem 0.65rem; font-size: 0.82rem; }
	button.on { background: var(--accent); color: #fff; box-shadow: 0 1px 3px rgb(29 59 39 / 0.25); }
	button:not(.on):not(:disabled):hover { color: var(--accent); }
	.dark { background: rgb(255 255 255 / 0.1); }
	.dark button { color: rgb(255 255 255 / 0.72); }
	.dark button:not(.on):not(:disabled):hover { color: #fff; }
	.dark button.on { background: #fff; color: #1d3b27; }
	button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
