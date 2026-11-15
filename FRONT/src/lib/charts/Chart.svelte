<script lang="ts">
	// Gráfico SVG ligero: líneas / barras / área, eje secundario opcional, bandas e interacción hover.
	export type Series = {
		name: string;
		color: string;
		values: (number | null)[];
		type?: 'line' | 'bar' | 'area';
		axis?: 'left' | 'right';
		dashed?: boolean;
		low?: (number | null)[]; // banda de rango (min/max)
		high?: (number | null)[];
	};
	type Band = { from: number; to: number; color: string; label?: string };

	let {
		labels,
		series,
		bands = [],
		height = 190,
		unit = '',
		unitRight = '',
		zeroLine = false,
		ticks = 6,
		format = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1))
	}: {
		labels: string[];
		series: Series[];
		bands?: Band[];
		height?: number;
		unit?: string;
		unitRight?: string;
		zeroLine?: boolean;
		ticks?: number;
		format?: (v: number) => string;
	} = $props();

	const W = 440;
	const P = { l: 34, r: 34, t: 8, b: 20 };
	const n = $derived(labels.length);
	const iw = $derived(W - P.l - (series.some((s) => s.axis === 'right') ? P.r : 12));
	const ih = $derived(height - P.t - P.b);

	function extent(axis: 'left' | 'right') {
		const vals: number[] = [];
		for (const s of series)
			if ((s.axis ?? 'left') === axis)
				for (const arr of [s.values, s.low ?? [], s.high ?? []]) for (const v of arr) if (v != null) vals.push(v);
		if (!vals.length) return null;
		let lo = Math.min(...vals), hi = Math.max(...vals);
		if (series.some((s) => (s.axis ?? 'left') === axis && s.type === 'bar') || zeroLine) lo = Math.min(lo, 0), hi = Math.max(hi, 0);
		if (lo === hi) hi = lo + 1;
		const pad = (hi - lo) * 0.08;
		return [lo < 0 ? lo - pad : lo === 0 ? 0 : lo - pad, hi + pad] as [number, number];
	}
	const L = $derived(extent('left'));
	const R = $derived(extent('right'));

	const x = (i: number) => P.l + (n <= 1 ? iw / 2 : ((i + 0.5) / n) * iw);
	const slot = $derived(iw / Math.max(n, 1));
	function y(v: number, axis: 'left' | 'right' = 'left') {
		const e = axis === 'left' ? L : R;
		if (!e) return 0;
		return P.t + ih - ((v - e[0]) / (e[1] - e[0])) * ih;
	}
	function path(vals: (number | null)[], axis: 'left' | 'right') {
		let d = '', pen = false;
		vals.forEach((v, i) => {
			if (v == null) { pen = false; return; }
			d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v, axis).toFixed(1)}`;
			pen = true;
		});
		return d;
	}
	function areaPath(hi: (number | null)[], lo: (number | null)[], axis: 'left' | 'right') {
		const idx = hi.map((v, i) => i).filter((i) => hi[i] != null && lo[i] != null);
		if (!idx.length) return '';
		const top = idx.map((i, k) => `${k ? 'L' : 'M'}${x(i)},${y(hi[i]!, axis)}`).join('');
		const bot = [...idx].reverse().map((i) => `L${x(i)},${y(lo[i]!, axis)}`).join('');
		return top + bot + 'Z';
	}
	function yTicks(e: [number, number] | null) {
		if (!e) return [];
		const step = (e[1] - e[0]) / 4;
		return [0, 1, 2, 3, 4].map((k) => e[0] + step * k);
	}
	const every = $derived(Math.max(1, Math.ceil(n / ticks)));

	let hover = $state<number | null>(null);
	let svg: SVGSVGElement;
	function move(ev: PointerEvent) {
		const r = svg.getBoundingClientRect();
		const px = ((ev.clientX - r.left) / r.width) * W;
		const i = Math.floor(((px - P.l) / iw) * n);
		hover = i >= 0 && i < n ? i : null;
	}
	const bars = $derived(series.filter((s) => s.type === 'bar'));
</script>

<div class="chart">
	<div class="legend">
		{#if unit}<span class="u">{unit}{unitRight ? ` · der. ${unitRight}` : ''}</span>{/if}
		{#each series as s}
			<span><i style="background:{s.color}" class:dash={s.dashed}></i>{s.name}</span>
		{/each}
		{#if hover != null}
			<span class="hv">
				<b>{labels[hover]}</b>
				{#each series as s}
					{#if s.values[hover] != null}<span style="color:{s.color}">{format(s.values[hover]!)}</span>{/if}
				{/each}
			</span>
		{/if}
	</div>
	<svg bind:this={svg} viewBox="0 0 {W} {height}" onpointermove={move} onpointerleave={() => (hover = null)} role="img">
		{#each bands as b}
			<rect x={x(b.from) - slot / 2} y={P.t} width={Math.max(slot, x(b.to) - x(b.from) + slot)} height={ih} fill={b.color} opacity="0.13">
				{#if b.label}<title>{b.label}</title>{/if}
			</rect>
		{/each}
		{#each yTicks(L) as t}
			<line x1={P.l} x2={P.l + iw} y1={y(t)} y2={y(t)} class="grid" />
			<text x={P.l - 6} y={y(t) + 3} text-anchor="end" class="tick">{format(t)}</text>
		{/each}
		{#each yTicks(R) as t}
			<text x={P.l + iw + 5} y={y(t, 'right') + 3} class="tick">{format(t)}</text>
		{/each}
		{#if L && L[0] < 0 && L[1] > 0}
			<line x1={P.l} x2={P.l + iw} y1={y(0)} y2={y(0)} class="zero" />
		{/if}
		{#each labels as lab, i}
			{#if i % every === 0}<text x={x(i)} y={height - 6} text-anchor="middle" class="tick">{lab}</text>{/if}
		{/each}

		{#each bars as s, k}
			{#each s.values as v, i}
				{#if v != null}
					{@const bw = (slot * 0.7) / bars.length}
					{@const bx = x(i) - (slot * 0.7) / 2 + k * bw}
					{@const y0 = y(Math.max(0, (s.axis === 'right' ? R : L)?.[0] ?? 0), s.axis)}
					<rect x={bx} width={Math.max(bw - 1, 1)} y={Math.min(y(v, s.axis), y0)} height={Math.abs(y0 - y(v, s.axis))} fill={s.color} rx="2" opacity={hover == null || hover === i ? 1 : 0.55} />
				{/if}
			{/each}
		{/each}
		{#each series as s}
			{#if s.low && s.high}
				<path d={areaPath(s.high, s.low, s.axis ?? 'left')} fill={s.color} opacity="0.14" />
			{/if}
			{#if s.type === 'area'}
				<path d={areaPath(s.values, s.values.map(() => Math.max(0, (s.axis === 'right' ? R : L)?.[0] ?? 0)), s.axis ?? 'left')} fill={s.color} opacity="0.18" />
			{/if}
			{#if s.type !== 'bar'}
				<path d={path(s.values, s.axis ?? 'left')} fill="none" stroke={s.color} stroke-width="2" stroke-dasharray={s.dashed ? '5 4' : undefined} stroke-linejoin="round" />
			{/if}
		{/each}
		{#if hover != null}
			<line x1={x(hover)} x2={x(hover)} y1={P.t} y2={P.t + ih} class="cursor" />
		{/if}
	</svg>
</div>

<style>
	.chart { width: 100%; }
	svg { width: 100%; height: auto; display: block; touch-action: pan-y; }
	.legend { display: flex; flex-wrap: wrap; gap: 0.25rem 0.9rem; font-size: 0.75rem; color: var(--ink-2); min-height: 1.2rem; margin-bottom: 0.25rem; }
	.legend i { display: inline-block; width: 10px; height: 3px; border-radius: 2px; margin-right: 0.3rem; vertical-align: middle; }
	.legend i.dash { background-image: linear-gradient(90deg, transparent 50%, var(--surface) 50%) !important; background-size: 4px 3px; }
	.hv { margin-left: auto; display: flex; gap: 0.5rem; font-variant-numeric: tabular-nums; }
	.grid { stroke: var(--line); stroke-width: 1; }
	.zero { stroke: var(--ink-2); stroke-width: 1; opacity: 0.5; }
	.cursor { stroke: var(--ink-2); stroke-dasharray: 3 3; }
	.u { font-weight: 600; }
	.tick { fill: var(--ink-2); font-size: 9.5px; font-family: var(--font); }
</style>
