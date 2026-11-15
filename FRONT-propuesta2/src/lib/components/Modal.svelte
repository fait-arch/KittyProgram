<script lang="ts">
	import type { Snippet } from 'svelte';
	let { title, onclose, wide = false, page = false, kicker = '', children }: { title: string; onclose: () => void; wide?: boolean; page?: boolean; kicker?: string; children: Snippet } = $props();
	function key(e: KeyboardEvent) { if (e.key === 'Escape' && !page) onclose(); }
</script>

<svelte:window onkeydown={key} />
{#if page}
	<!-- Misma vista, como página completa (secciones del menú lateral) -->
	<section class="pg" aria-label={title}>
		<header class="ph">
			{#if kicker}<small>{kicker}</small>{/if}
			<h1>{title}</h1>
		</header>
		<div class="pbody">{@render children()}</div>
	</section>
{:else}
	<div class="backdrop" onclick={onclose} role="presentation"></div>
	<div class="modal" class:wide role="dialog" aria-modal="true" aria-label={title}>
		<header>
			<h2>{title}</h2>
			<button class="btn sm" onclick={onclose} aria-label="Cerrar">✕</button>
		</header>
		<div class="body">{@render children()}</div>
	</div>
{/if}

<style>
	.backdrop { position: fixed; inset: 0; background: rgb(31 42 34 / 0.4); backdrop-filter: blur(2px); z-index: 50; }
	.modal {
		position: fixed; z-index: 51; left: 50%; top: 50%; transform: translate(-50%, -50%);
		width: min(560px, calc(100vw - 32px)); max-height: calc(100vh - 48px);
		background: var(--surface); border-radius: 18px; box-shadow: var(--shadow);
		display: flex; flex-direction: column; overflow: hidden;
	}
	.modal.wide { width: min(920px, calc(100vw - 32px)); }
	header { display: flex; justify-content: space-between; align-items: center; padding: 1.1rem 1.4rem; border-bottom: 1px solid var(--line); }
	.pg { max-width: 1040px; margin: 0 auto; padding: 1.6rem 1.4rem 3rem; display: flex; flex-direction: column; gap: 1.2rem; }
	.ph { display: flex; flex-direction: column; gap: 0.25rem; }
	.ph small { font: 600 0.72rem/1 var(--font); text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-2); }
	.ph h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); }
	.pbody { display: flex; flex-direction: column; gap: 1.25rem; }
	.body { padding: 1.25rem 1.4rem 1.5rem; overflow: auto; display: flex; flex-direction: column; gap: 1.25rem; }
</style>
