<script lang="ts">
	let { page = false }: { page?: boolean } = $props();
	// /meta + /crops + /crops/{crop}/requirements + /pathogens + /phenology + /strategies + /scenarios
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { usd } from '#lib/fmt';
	import Modal from './Modal.svelte';
	import Async from './Async.svelte';
	import Section from './Section.svelte';
	import Segmented from './Segmented.svelte';

	let tab = $state('datos');
	const meta = api.meta(app.crop);
	const crops = api.crops();
	const req = api.requirements(app.crop);
	const pats = api.pathogens(app.crop);
	const strat = api.strategyCatalog();
	const scen = api.scenarios(app.crop);
	const TABS = [{ id: 'datos', label: 'Datos y modelo' }, { id: 'cultivo', label: 'El cultivo' }, { id: 'estrategias', label: 'Estrategias' }, { id: 'escenarios', label: 'Escenarios' }];
</script>

<Modal title="Cómo funciona" wide {page} kicker="Metodología y fuentes" onclose={() => (app.modal = null)}>
	<Segmented options={TABS} bind:value={tab} />
	{#if tab === 'datos'}
		<Async promise={meta} height={200}>
			{#snippet children(m: any)}
				{#if m.model}
					<div class="grid3">
						<div class="kpi"><div class="label">Modelo</div><div class="value sm">{m.model.name}</div><div class="sub">{m.model.algorithm}</div></div>
						<div class="kpi"><div class="label">Error medio</div><div class="value sm">± {m.model.metrics?.mae ?? '—'} pts</div><div class="sub">mejora vs base {m.model.metrics?.skill_vs_baseline ?? '—'}</div></div>
						<div class="kpi"><div class="label">Entrenado con</div><div class="value sm">{m.model.train_start_year}–{m.model.train_end_year}</div><div class="sub">{m.model.n_samples} observaciones</div></div>
					</div>
				{/if}
				<Section title="Fuentes">
					<ul class="src">{#each m.sources as s}<li><a href={s.url} target="_blank" rel="noopener">{s.name}</a><small>{s.provider}{s.spatial_res_m ? ` · ${s.spatial_res_m >= 1000 ? s.spatial_res_m / 1000 + ' km' : s.spatial_res_m + ' m'}` : ''}</small></li>{/each}</ul>
				</Section>
				<details><summary>Variables ({m.variables.length})</summary><table><tbody>{#each m.variables as v}<tr><td>{v.name}</td><td>{v.unit}</td><td><small>{v.source_id}</small></td></tr>{/each}</tbody></table></details>
				<Section title="Limitaciones"><ul>{#each m.limitations as l}<li>{l}</li>{/each}</ul></Section>
				<p class="disclaimer">{m.attribution}<br />{m.disclaimer}</p>
			{/snippet}
		</Async>
	{:else if tab === 'cultivo'}
		<Async promise={Promise.all([crops, req, pats])} height={200}>
			{#snippet children([cs, r, ps]: any)}
				{@const c = cs.find((x: any) => x.id === app.crop)}
				{#if c}<p><b>{c.name_es}</b> <i>({c.scientific_name})</i> · {c.family} · {c.is_perennial ? 'perenne' : 'anual'} · regiones: {c.region?.join(', ')}</p>{/if}
				<Section title="Lo que necesita" hint={r.source}>
					<table>
						<thead><tr><th>Parámetro</th><th>Óptimo</th><th>Límite</th></tr></thead>
						<tbody>{#each r.numeric as n}<tr><td>{n.label}</td><td>{n.opt_min ?? '…'} – {n.opt_max ?? '…'} {n.unit}</td><td>{n.abs_min ?? '…'} – {n.abs_max ?? '…'}</td></tr>{/each}
						{#each r.categorical ?? [] as k}<tr><td>{k.label}</td><td colspan="2">{k.value}</td></tr>{/each}</tbody>
					</table>
				</Section>
				<Section title="Enfermedades vigiladas">
					{#each ps as p}<div class="pat"><b>{p.name_es}</b> <i>{p.scientific_name}</i><p>{p.description}</p><small>Día favorable: {p.rule_text} · ataca {p.organ_affected} · se dispersa por {p.spread_by?.join(', ')}</small></div>{/each}
				</Section>
			{/snippet}
		</Async>
	{:else if tab === 'estrategias'}
		<Async promise={strat} height={200}>
			{#snippet children(ss: any[])}
				<div class="cards">
					{#each ss as s}
						<div class="card">
							<div class="spread"><b>{s.name_es}</b><small>{usd(s.cost_usd_ha_year, true)}/ha·año</small></div>
							<p class="muted">{s.description}</p>
							{#if s.effects?.length}<small>Reduce: {s.effects.map((e: any) => `${e.target} ${e.reduction_pct_min ?? e.reduction_pct?.[0] ?? ''}–${e.reduction_pct_max ?? e.reduction_pct?.[1] ?? ''} %`).join(' · ')}</small>{/if}
							{#if s.applies_to_zones}<small>Zonas: {s.applies_to_zones.join(', ')}</small>{/if}
							{#if s.evidence}<small>{s.evidence}</small>{/if}
						</div>
					{/each}
				</div>
			{/snippet}
		</Async>
	{:else}
		<Async promise={scen} height={200}>
			{#snippet children(ss: any[])}
				<table>
					<thead><tr><th>Escenario</th><th>Periodo</th><th>Descripción</th><th></th></tr></thead>
					<tbody>{#each ss as s}<tr><td><b>{s.name_es}</b></td><td>{s.period?.join('–')}</td><td>{s.description}</td><td>{s.available ? '✓' : 'sin datos'}</td></tr>{/each}</tbody>
				</table>
			{/snippet}
		</Async>
	{/if}
</Modal>

<style>
	.value.sm { font-size: 1.1rem; }
	.src { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0.5rem 1rem; }
	.src li { display: flex; flex-direction: column; }
	ul { margin: 0; padding-left: 1.1rem; }
	details { font-size: 0.85rem; }
	summary { cursor: pointer; color: var(--ink-2); }
	.pat { padding: 0.6rem 0; border-bottom: 1px solid var(--line); }
	.pat:last-child { border: 0; }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 0.75rem; }
	.cards .card { display: flex; flex-direction: column; gap: 0.35rem; }
</style>
