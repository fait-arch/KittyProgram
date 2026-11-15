<script lang="ts">
	// Supabase Auth (email + contraseña) → JWT para POST /observations
	import { supabaseLogin, supabaseConfigured } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import Modal from './Modal.svelte';

	let email = $state(''), password = $state(''), token = $state('');
	let err = $state(''), busy = $state(false);
	async function login(e: SubmitEvent) {
		e.preventDefault(); err = ''; busy = true;
		try {
			const r = await supabaseLogin(email, password);
			app.setSession(r.token, r.email);
			app.modal = null;
		} catch (x) { err = (x as Error).message; } finally { busy = false; }
	}
	function useToken() { if (token.trim()) { app.setSession(token.trim(), 'token manual'); app.modal = null; } }
</script>

<Modal title={app.token ? 'Tu sesión' : 'Iniciar sesión'} onclose={() => (app.modal = null)}>
	{#if app.token}
		<p>Sesión activa como <b>{app.userEmail}</b>. Puedes reportar observaciones de campo.</p>
		<button class="btn" onclick={() => { app.setSession('', ''); app.modal = null; }}>Cerrar sesión</button>
	{:else}
		<p class="muted">Para técnicos del MAG/INIAP y agricultores que reportan lo que ven en el campo.</p>
		{#if supabaseConfigured}
			<form class="f" onsubmit={login}>
				<input type="email" placeholder="Correo" bind:value={email} required autocomplete="email" />
				<input type="password" placeholder="Contraseña" bind:value={password} required autocomplete="current-password" />
				<button class="btn primary" disabled={busy}>{busy ? 'Entrando…' : 'Entrar'}</button>
				{#if err}<p class="err">{err}</p>{/if}
			</form>
		{:else}
			<p class="err">Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en FRONT/.env.</p>
		{/if}
		<details>
			<summary>Tengo un token de acceso</summary>
			<div class="f"><input type="text" placeholder="Pega aquí el JWT" bind:value={token} /><button class="btn" onclick={useToken}>Usar token</button></div>
		</details>
	{/if}
</Modal>

<style>
	.f { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.5rem; }
	summary { cursor: pointer; color: var(--ink-2); font-size: 0.85rem; }
</style>
