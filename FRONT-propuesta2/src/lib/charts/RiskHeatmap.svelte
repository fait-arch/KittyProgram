<script lang="ts">
	import { MONTHS, PATHOGEN_LABEL } from '#lib/fmt';
	import { app } from '#lib/state.svelte';

	// months: [{month:1, monilia:0.8, ...}] · riskWindow: meses de la ventana de riesgo fenológica
	let { months, pathogens, riskWindow = [], critical = [] }: {
		months: Record<string, number>[];
		pathogens: string[];
		riskWindow?: number[];
		critical?: number[];
	} = $props();

	const color = (v: number) => {
		const t = Math.max(0, Math.min(1, v));
		// blanco verdoso → ocre → café → vino
		const low = app.theme === 'dark' ? [36, 52, 41] : [238, 241, 236];
		const stops = [low, [194, 160, 90], [139, 94, 60], [110, 31, 28]];
		const p = t * (stops.length - 1), i = Math.min(Math.floor(p), stops.length - 2), f = p - i;
		const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
		return `rgb(${c.join(',')})`;
	};
</script>

<div class="hm">
	<div></div>
	{#each MONTHS as m, i}
		<div class="mh" class:win={riskWindow.includes(i + 1)} class:crit={critical.includes(i + 1)}>{m[0]}</div>
	{/each}
	{#each pathogens as p}
		<div class="pl">{PATHOGEN_LABEL[p] ?? p}</div>
		{#each MONTHS as m, i}
			{@const v = months.find((r) => r.month === i + 1)?.[p] ?? 0}
			<div class="cell" style="background:{color(v)}" title="{PATHOGEN_LABEL[p] ?? p} · {m}: {Math.round(v * 100)} %"></div>
		{/each}
	{/each}
</div>
<div class="foot">
	<span><i class="w"></i>Ventana de riesgo del cultivo</span>
	{#if critical.length}<span><i class="c"></i>Meses críticos (IA)</span>{/if}
	<span class="scale">Bajo <b style="background:linear-gradient(90deg,{color(0)},{color(0.5)},{color(1)})"></b> Alto</span>
</div>

<style>
	.hm { display: grid; grid-template-columns: 7.5rem repeat(12, 1fr); gap: 3px; align-items: center; }
	.mh { text-align: center; font-size: 0.72rem; color: var(--ink-2); padding-bottom: 2px; border-bottom: 2px solid transparent; }
	.mh.win { border-bottom-color: var(--accent-2); color: var(--ink); font-weight: 600; }
	.mh.crit { color: var(--bad); }
	.pl { font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.cell { height: 22px; border-radius: 4px; }
	.foot { display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.72rem; color: var(--ink-2); margin-top: 0.5rem; align-items: center; }
	.foot i { display: inline-block; width: 12px; height: 3px; margin-right: 4px; vertical-align: middle; }
	.foot i.w { background: var(--accent-2); }
	.foot i.c { background: var(--bad); }
	.scale { margin-left: auto; display: inline-flex; align-items: center; gap: 0.35rem; }
	.scale b { width: 60px; height: 8px; border-radius: 4px; display: inline-block; }
</style>
