<script lang="ts">
	// /areas/{id}/insights (bajo demanda: tarda 10–40 s) + POST /areas/{id}/ask (chat)
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { MONTHS, errMsg } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	let { id }: { id: string } = $props();

	let insights = $state<Promise<any> | null>(null);
	const generate = () => (insights = api.insights(id, app.scenario, app.crop, app.prioritiesParam));

	type Msg = { role: 'user' | 'assistant'; content: string };
	let chat = $state<Msg[]>([]);
	let q = $state('');
	let busy = $state(false);
	let chatErr = $state('');
	const SUGGEST = ['¿Cuándo debo hacer la poda?', '¿Qué hago si llueve mucho en febrero?', '¿Vale la pena invertir este año?'];

	async function send(text = q) {
		text = text.trim();
		if (!text || busy) return;
		chatErr = ''; busy = true; q = '';
		const history = chat.slice(-20);
		chat = [...chat, { role: 'user', content: text }];
		try {
			const r: any = await api.ask(id, { question: text, scenario: app.scenario, crop: app.crop, history });
			chat = [...chat, { role: 'assistant', content: r.answer }];
		} catch (e) {
			chatErr = errMsg(e);
		} finally { busy = false; }
	}
	const ALERT: Record<string, string> = { bajo: 'var(--good)', medio: 'var(--warn)', alto: '#a99f6a', muy_alto: 'var(--bad)', critico: 'var(--bad)' };
</script>

<Section title="Diagnóstico del cantón" hint="La IA interpreta los números de la API; no inventa datos">
	{#if !insights}
		<button class="btn primary" onclick={generate}>✦ Generar diagnóstico</button>
	{:else}
		<Async promise={insights} height={200} loadingText="La IA está analizando el cantón (puede tardar hasta 40 s)…">
			{#snippet children(r: any)}
				<div class="sum" style="--c:{ALERT[r.nivel_alerta] ?? 'var(--accent)'}">
					<span class="pill">Alerta {r.nivel_alerta}</span>
					<p>{r.resumen}</p>
				</div>
				{#if r.meses_criticos?.length}<p class="muted">Meses críticos: <b>{r.meses_criticos.map((m: number) => MONTHS[m - 1]).join(', ')}</b></p>{/if}
				{#if r.recomendaciones?.length}
					<h4>Recomendaciones</h4>
					<ul class="recs">
						{#each r.recomendaciones as x}
							<li><b>{x.accion}</b><span class="pill p-{x.prioridad}">{x.prioridad}</span><p>{x.por_que}</p><small>🗓 {x.cuando}</small></li>
						{/each}
					</ul>
				{/if}
				{#if r.hallazgos?.length}
					<h4>Hallazgos</h4>
					<ul class="plain">{#each r.hallazgos as h}<li><b>{h.titulo}.</b> {h.detalle} <small class="muted">{h.evidencia}</small></li>{/each}</ul>
				{/if}
				{#if r.validar_con_experto?.length}<details><summary>Validar con un técnico</summary><ul>{#each r.validar_con_experto as v}<li>{v}</li>{/each}</ul></details>{/if}
				{#if r.vacios_de_datos?.length}<details><summary>Vacíos de datos</summary><ul>{#each r.vacios_de_datos as v}<li>{v}</li>{/each}</ul></details>{/if}
				<p class="disclaimer">{r.provider} · {r.model} · {r.disclaimer}</p>
				<button class="btn sm" onclick={generate}>↻ Regenerar con mis prioridades</button>
			{/snippet}
		</Async>
	{/if}
</Section>

<Section title="Pregunta lo que quieras">
	<div class="chat">
		{#each chat as m}<div class="msg {m.role}">{m.content}</div>{/each}
		{#if busy}<div class="msg assistant typing">…</div>{/if}
		{#if chatErr}<p class="err">{chatErr}</p>{/if}
	</div>
	{#if !chat.length}
		<div class="row">{#each SUGGEST as s}<button class="btn sm" onclick={() => send(s)}>{s}</button>{/each}</div>
	{/if}
	<form class="ask" onsubmit={(e) => { e.preventDefault(); send(); }}>
		<input type="text" bind:value={q} placeholder="Escribe tu pregunta…" disabled={busy} />
		<button class="btn primary" disabled={busy || !q.trim()}>Enviar</button>
	</form>
</Section>

<style>
	.sum { border-left: 3px solid var(--c); padding-left: 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
	.sum .pill { align-self: flex-start; background: var(--c); color: #fff; text-transform: capitalize; }
	h4 { margin: 0.4rem 0 0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); }
	.recs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
	.recs li { background: var(--surface-2); border-radius: 12px; padding: 0.7rem 0.85rem; }
	.recs .pill { margin-left: 0.5rem; background: var(--surface); }
	.p-alta { color: var(--bad); }
	.plain { margin: 0; padding-left: 1.1rem; display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.88rem; }
	details { font-size: 0.85rem; color: var(--ink-2); }
	.chat { display: flex; flex-direction: column; gap: 0.5rem; }
	.msg { padding: 0.6rem 0.85rem; border-radius: 14px; max-width: 88%; white-space: pre-wrap; font-size: 0.9rem; }
	.msg.user { align-self: flex-end; background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
	.msg.assistant { align-self: flex-start; background: var(--surface-2); border-bottom-left-radius: 4px; }
	.typing { animation: pulse 1s infinite; }
	@keyframes pulse { 50% { opacity: 0.4; } }
	.ask { display: flex; gap: 0.5rem; }
	.ask input { flex: 1; border-radius: 999px; padding-left: 0.9rem; }
</style>
