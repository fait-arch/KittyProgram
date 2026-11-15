<script lang="ts">
	// /areas/{id}/strategies con prioridades del agricultor (reordena en vivo)
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { pct, usd, PRIORITY_LABEL } from '#lib/fmt';
	import Async from '#lib/components/Async.svelte';
	import Section from '#lib/components/Section.svelte';
	let { id }: { id: string } = $props();

	let committed = $state(app.prioritiesParam);
	$effect(() => {
		const p = app.prioritiesParam;
		const t = setTimeout(() => (committed = p), 350);
		return () => clearTimeout(t);
	});
	const data = $derived.by(() => { void app.refresh; return api.strategies(id, app.scenario, app.crop, committed); });
	let expanded = $state<string | null>(null);
</script>

<Section title="¿Qué te importa más?" hint="Mueve las barras y las opciones se reordenan">
	<div class="prio">
		{#each Object.keys(app.priorities) as k}
			<label><span>{PRIORITY_LABEL[k]}</span><input type="range" min="0" max="5" step="1" bind:value={app.priorities[k]} /><b>{app.priorities[k]}</b></label>
		{/each}
	</div>
</Section>

<Async promise={data} height={240}>
	{#snippet children(s: any)}
		<p class="muted">Sin hacer nada se perdería <b>{pct(s.baseline_loss_pct)}</b> de la cosecha ({usd(s.baseline_loss_usd)}).</p>
		<ol class="list">
			{#each s.items as it, i}
				<li class:current={it.is_current}>
					<button class="head" onclick={() => (expanded = expanded === it.strategy_id ? null : it.strategy_id)} aria-expanded={expanded === it.strategy_id}>
						<span class="rank">{it.is_current ? '—' : i + 1}</span>
						<span class="name"><b>{it.name_es}</b><small>{it.is_current ? 'Referencia' : it.why}</small></span>
						<span class="nums">
							<b>{pct(it.expected_loss_pct)}</b>
							<small class:tag-ok={it.net_benefit_usd > 0} class:tag-bad={it.net_benefit_usd < 0}>{it.is_current ? 'pérdida' : `neto ${usd(it.net_benefit_usd)}`}</small>
						</span>
					</button>
					{#if expanded === it.strategy_id && !it.is_current}
						<div class="more">
							<p>{it.description}</p>
							<div class="grid3">
								<div class="kpi"><div class="label">Evita</div><div class="value sm">{usd(it.avoided_loss_usd)}</div></div>
								<div class="kpi"><div class="label">Cuesta</div><div class="value sm">{usd(it.cost_total_usd)}</div><div class="sub">{usd(it.cost_usd_ha_year, true)}/ha·año</div></div>
								<div class="kpi"><div class="label">Reduce</div><div class="value sm">{pct(it.loss_reduction_pct)}</div></div>
							</div>
							{#if it.benefits?.length}<h4>Beneficios</h4><ul>{#each it.benefits as b}<li>{b}</li>{/each}</ul>{/if}
							{#if it.risks?.length}<h4>Riesgos</h4><ul>{#each it.risks as b}<li>{b}</li>{/each}</ul>{/if}
							{#if it.evidence?.length}<h4>Evidencia</h4><ul class="muted">{#each it.evidence as e}<li>{e.statement} <small>({e.source_id})</small></li>{/each}</ul>{/if}
							{#if it.data_gaps?.length}<p class="muted"><small>⚠ {it.data_gaps.join(' · ')}</small></p>{/if}
							{#if !it.validated}<span class="pill">Supuesto por validar</span>{/if}
						</div>
					{/if}
				</li>
			{/each}
		</ol>
	{/snippet}
</Async>

<style>
	.prio { display: flex; flex-direction: column; gap: 0.35rem; }
	.prio label { display: grid; grid-template-columns: 9.5rem 1fr 1.2rem; align-items: center; gap: 0.75rem; font-size: 0.85rem; }
	.prio b { text-align: right; font-variant-numeric: tabular-nums; }
	.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.6rem; }
	.list li { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
	.list li.current { border-style: dashed; opacity: 0.85; }
	.head { width: 100%; display: grid; grid-template-columns: 1.6rem 1fr auto; gap: 0.75rem; align-items: center; padding: 0.75rem 0.9rem; border: 0; background: none; cursor: pointer; text-align: left; }
	.rank { font-family: var(--display); font-size: 1.2rem; color: var(--accent); text-align: center; }
	.name { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
	.name small { color: var(--ink-2); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
	.nums { display: flex; flex-direction: column; align-items: flex-end; }
	.nums small { font-size: 0.75rem; color: var(--ink-2); }
	.more { padding: 0 0.9rem 0.9rem 3.25rem; display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.88rem; }
	.more h4 { margin: 0.3rem 0 0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); }
	.more ul { margin: 0; padding-left: 1.1rem; }
	.value.sm { font-size: 1.05rem; }
	.pill { align-self: flex-start; }
</style>
