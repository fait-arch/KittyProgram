<script lang="ts">
	// Mapa SVG liviano (sin teselas): los cantones de un área coloreados, con el elegido resaltado.
	let { features, colors, selectedId = null, height = 180, onpick }: {
		features: any[]; colors: Map<string, string>; selectedId?: string | null; height?: number; onpick?: (id: string, name: string) => void;
	} = $props();

	const W = 320;
	const geo = $derived.by(() => {
		let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
		const walk = (c: any) => (typeof c[0] === 'number' ? ((x0 = Math.min(x0, c[0])), (x1 = Math.max(x1, c[0])), (y0 = Math.min(y0, c[1])), (y1 = Math.max(y1, c[1]))) : c.forEach(walk));
		features.forEach((f) => walk(f.geometry.coordinates));
		const k = Math.min((W - 8) / (x1 - x0 || 1), (height - 8) / (y1 - y0 || 1));
		const ox = (W - (x1 - x0) * k) / 2, oy = (height - (y1 - y0) * k) / 2;
		const ring = (r: number[][]) => r.map(([x, y], i) => `${i ? 'L' : 'M'}${(ox + (x - x0) * k).toFixed(1)},${(oy + (y1 - y) * k).toFixed(1)}`).join('') + 'Z';
		const path = (g: any) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).map((p: number[][][]) => p.map(ring).join('')).join('');
		return features.map((f) => ({ id: f.properties.id, name: f.properties.name, d: path(f.geometry) }));
	});
	const sel = $derived(geo.find((g) => g.id === selectedId));
</script>

<svg viewBox="0 0 {W} {height}" role="img" aria-label="Mapa de cantones">
	{#each geo as g (g.id)}
		<path d={g.d} fill={colors.get(g.id) ?? 'var(--surface-2)'} stroke="var(--surface)" stroke-width="0.6" fill-rule="evenodd"
			class="pick" onclick={() => onpick?.(g.id, g.name)} role="button" tabindex="0"
			onkeydown={(e) => e.key === 'Enter' && onpick?.(g.id, g.name)}><title>{g.name}</title></path>
	{/each}
	{#if sel}<path d={sel.d} fill="none" stroke="var(--ink)" stroke-width="2.2" fill-rule="evenodd" pointer-events="none" />{/if}
</svg>

<style>
	svg { width: 100%; height: auto; display: block; }
	.pick { cursor: pointer; }
	.pick:hover { opacity: 0.8; }
</style>
