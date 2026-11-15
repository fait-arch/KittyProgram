<script lang="ts">
	// Compartir: enlace con el mismo mapa (escenario, cantón, capa, vista), WhatsApp, menú del sistema o ficha impresa.
	import { app } from '#lib/state.svelte';
	import Modal from './Modal.svelte';
	import Icon from './Icon.svelte';

	const url = app.url;
	let copied = $state(false);
	const text = app.selectedName
		? `Pérdida estimada de cacao en ${app.selectedName} · CacaoResiliente`
		: 'Mapa de pérdidas de cacao por El Niño · CacaoResiliente';
	async function copy() {
		try { await navigator.clipboard.writeText(url); copied = true; setTimeout(() => (copied = false), 2000); } catch { /* sin portapapeles */ }
	}
	async function native() {
		try { await navigator.share({ title: 'CacaoResiliente', text, url }); } catch { /* cancelado */ }
	}
	function print() { app.modal = null; setTimeout(() => window.print(), 300); }
	const canShare = typeof navigator !== 'undefined' && 'share' in navigator;
</script>

<Modal title="Compartir" onclose={() => (app.modal = null)}>
	<p class="muted">El enlace abre exactamente este mapa: escenario, {app.selectedName ? `cantón ${app.selectedName}, ` : ''}capa y vista.</p>
	<div class="link">
		<input type="text" readonly value={url} onfocus={(e) => e.currentTarget.select()} aria-label="Enlace" />
		<button class="btn primary" onclick={copy}><Icon name={copied ? 'check' : 'link'} size={16} />{copied ? 'Copiado' : 'Copiar'}</button>
	</div>
	<div class="opts">
		<a class="opt" href={`https://wa.me/?text=${encodeURIComponent(`${text}\n${url}`)}`} target="_blank" rel="noopener noreferrer">
			<span class="ic"><Icon name="chat" /></span><span><b>WhatsApp</b><small>Enviar el enlace a un contacto o grupo</small></span>
		</a>
		{#if canShare}
			<button class="opt" onclick={native}><span class="ic"><Icon name="share" /></span><span><b>Más opciones</b><small>Menú de compartir del teléfono</small></span></button>
		{/if}
		<button class="opt" onclick={print}><span class="ic"><Icon name="print" /></span><span><b>Ficha para imprimir</b><small>{app.selectedName ? 'Mapa y ficha del cantón' : 'Mapa actual'} · guardar como PDF</small></span></button>
	</div>
</Modal>

<style>
	.link { display: flex; gap: 0.5rem; }
	.link input { flex: 1; font-size: 0.85rem; }
	.opts { display: flex; flex-direction: column; gap: 0.4rem; }
	.opt { display: flex; gap: 0.7rem; align-items: center; padding: 0.6rem; border: 1px solid var(--line); border-radius: 12px; background: none; cursor: pointer; text-align: left; text-decoration: none; color: inherit; }
	.opt:hover { border-color: var(--accent); background: var(--surface-2); }
	.opt span:last-child { display: flex; flex-direction: column; }
	.opt small { color: var(--ink-2); }
	.ic { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent); flex-shrink: 0; }
</style>
