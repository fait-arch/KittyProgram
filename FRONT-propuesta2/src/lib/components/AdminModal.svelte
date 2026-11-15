<script lang="ts">
	// /health (detalle) + POST /admin/cache/clear + POST /admin/model/reload
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { errMsg } from '#lib/fmt';
	import Modal from './Modal.svelte';
	import Async from './Async.svelte';
	import Section from './Section.svelte';

	let health = $state(api.health());
	let key = $state(app.adminKey);
	let out = $state(''), err = $state(''), busy = $state(false);
	const auth = () => ({ adminKey: key || undefined, token: !key ? app.token || undefined : undefined });

	async function run(fn: typeof api.adminCacheClear, label: string) {
		out = err = ''; busy = true;
		app.setAdminKey(key);
		try {
			const r = await fn(auth());
			out = `${label}: ${JSON.stringify(r)}`;
			app.refresh++;
			health = api.health();
		} catch (e) { err = errMsg(e); } finally { busy = false; }
	}
	const ok = (b: boolean) => (b ? '✓' : '✕');
</script>

<Modal title="Estado del sistema" onclose={() => (app.modal = null)}>
	<Async promise={health} height={120}>
		{#snippet children(h: any)}
			<ul class="st">
				<li><span class:tag-ok={h.status === 'ok'} class:tag-warn={h.status !== 'ok'}>●</span> API <b>{h.status}</b> <small>v{h.version} · datos {h.data_source}</small></li>
				<li><span class:tag-ok={h.database?.ok} class:tag-bad={!h.database?.ok}>{ok(h.database?.ok)}</span> Base de datos {#if h.database?.error}<small>{h.database.error}</small>{/if}</li>
				<li><span class:tag-ok={h.model?.loaded} class:tag-warn={!h.model?.loaded}>{ok(h.model?.loaded)}</span> Modelo ML {h.model?.version ?? ''} {#if h.model?.error}<small>{h.model.error}</small>{/if}</li>
				<li><span class:tag-ok={h.ai?.configured} class:tag-bad={!h.ai?.configured}>{ok(h.ai?.configured)}</span> IA <small>{h.ai?.provider} · {h.ai?.model}</small></li>
			</ul>
		{/snippet}
	</Async>

	<Section title="Administración" hint="Requiere X-Admin-Key o sesión con un email administrador">
		<input type="password" placeholder="Clave de administrador (X-Admin-Key)" bind:value={key} autocomplete="off" />
		<div class="row">
			<button class="btn" disabled={busy} onclick={() => run(api.adminCacheClear, 'Caché vaciada')}>Vaciar caché</button>
			<button class="btn" disabled={busy} onclick={() => run(api.adminModelReload, 'Modelo recargado')}>Recargar modelo</button>
		</div>
		{#if out}<pre>{out}</pre>{/if}
		{#if err}<p class="err">{err}</p>{/if}
	</Section>
</Modal>

<style>
	.st { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
	.st small { display: block; margin-left: 1.2rem; word-break: break-word; }
	pre { white-space: pre-wrap; word-break: break-all; font-size: 0.78rem; background: var(--surface-2); padding: 0.6rem; border-radius: 8px; margin: 0; }
</style>
