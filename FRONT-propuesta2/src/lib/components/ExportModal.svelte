<script lang="ts">
	// Exportar en el navegador: GeoJSON + estilo .qml (mismo nombre → QGIS lo aplica al abrir), SLD, CSV o PDF.
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import Modal from './Modal.svelte';
	import Icon from './Icon.svelte';

	type Fmt = 'geojson' | 'sld' | 'csv' | 'pdf';
	let fmt = $state<Fmt>('geojson');
	let scenarios = $state<any[]>([]);
	let chosen = $state<Record<string, boolean>>({ [app.scenario]: true });
	let zones = $state(false);
	let busy = $state(false), msg = $state(''), err = $state('');
	$effect(() => { api.scenarios(app.crop).then((s) => (scenarios = s.filter((x: any) => x.available !== false))).catch(() => {}); });

	const FORMATS: { id: Fmt; name: string; desc: string; icon: string }[] = [
		{ id: 'geojson', name: 'GeoJSON + estilo .qml', desc: 'Arrastra los dos archivos juntos a QGIS: la leyenda sale lista.', icon: 'layers' },
		{ id: 'sld', name: 'Solo estilo SLD 1.1', desc: 'Para GeoServer u otros SIG.', icon: 'book' },
		{ id: 'csv', name: 'Tabla CSV', desc: 'Para Excel o LibreOffice: una fila por cantón y escenario.', icon: 'download' },
		{ id: 'pdf', name: 'Mapa en PDF', desc: 'Imprime o guarda como PDF la vista actual.', icon: 'print' }
	];

	function save(blob: Blob, name: string) {
		const a = document.createElement('a');
		a.href = URL.createObjectURL(blob); a.download = name;
		document.body.appendChild(a); a.click(); a.remove();
		setTimeout(() => URL.revokeObjectURL(a.href), 2000);
	}
	async function style(file: string, as: string) {
		const r = await fetch(`/qgis/${file}`);
		save(new Blob([await r.text()], { type: 'application/xml' }), as);
	}
	const prov = (p: any) => p.province_name ?? p.province?.name ?? p.province ?? '';

	async function run() {
		msg = err = ''; busy = true;
		try {
			if (fmt === 'pdf') { app.modal = null; setTimeout(() => window.print(), 300); return; }
			if (fmt === 'sld') {
				await style('perdida_cacao.sld', 'perdida_cacao.sld');
				if (zones) await style('zonas_2050.sld', 'zonas_2050.sld');
				msg = 'Estilo descargado.'; return;
			}
			const ids = Object.keys(chosen).filter((k) => chosen[k]);
			const areas: any = await api.areasGeojson({ kind: 'canton', province: app.province || undefined });
			const geo = new Map(areas.features.map((f: any) => [f.properties.id, f]));
			if (fmt === 'csv') {
				const rows = [['canton', 'provincia', 'escenario', 'loss_pct', 'loss_p10', 'loss_p90', 'clase', 'loss_t', 'loss_usd'].join(',')];
				for (const sc of ids) {
					const l: any = await api.losses({ scenario: sc, province: app.province || undefined, crop: app.crop });
					for (const i of l.items) {
						const f: any = geo.get(i.area_id);
						rows.push([f?.properties.name ?? i.name, f ? prov(f.properties) : '', sc, i.loss_pct, i.loss_pct_low, i.loss_pct_high, i.risk_class, Math.round(i.loss_t ?? 0), Math.round(i.loss_usd ?? 0)]
							.map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','));
					}
				}
				save(new Blob(['﻿' + rows.join('\n')], { type: 'text/csv;charset=utf-8' }), 'cacaoresiliente_perdidas.csv');
				msg = `CSV con ${rows.length - 1} filas.`; return;
			}
			let n = 0;
			for (const sc of ids) {
				const l: any = await api.losses({ scenario: sc, province: app.province || undefined, crop: app.crop });
				const name = `perdida_${sc}`;
				const fc = {
					type: 'FeatureCollection', name,
					crs: { type: 'name', properties: { name: 'urn:ogc:def:crs:OGC:1.3:CRS84' } },
					features: l.items.filter((i: any) => geo.has(i.area_id)).map((i: any) => {
						const f: any = geo.get(i.area_id);
						return { type: 'Feature', geometry: f.geometry, properties: {
							canton: f.properties.name, provincia: prov(f.properties), escenario: sc, loss_pct: i.loss_pct,
							loss_p10: i.loss_pct_low, loss_p90: i.loss_pct_high, clase: i.risk_class, fuente: `CacaoResiliente API · modelo ${l.model?.name ?? l.model ?? ''}` } };
					})
				};
				save(new Blob([JSON.stringify(fc)], { type: 'application/geo+json' }), `${name}.geojson`);
				await style('perdida_cacao.qml', `${name}.qml`); n += 2;
			}
			if (zones) {
				const z: any = await api.zones(app.future, app.crop, app.province || undefined);
				const by = new Map(z.items.map((i: any) => [i.area_id, i]));
				const fc = { type: 'FeatureCollection', name: 'zonas_2050', features: areas.features.filter((f: any) => by.has(f.properties.id)).map((f: any) => ({
					type: 'Feature', geometry: f.geometry, properties: { canton: f.properties.name, provincia: prov(f.properties), zona_2050: (by.get(f.properties.id) as any).zone_class, escenario: app.future } })) };
				save(new Blob([JSON.stringify(fc)], { type: 'application/geo+json' }), 'zonas_2050.geojson');
				await style('zonas_2050.qml', 'zonas_2050.qml'); n += 2;
			}
			msg = `Descargados ${n} archivos. Arrástralos juntos a QGIS.`;
		} catch (e: any) { err = e?.message ?? 'No se pudo exportar'; } finally { busy = false; }
	}
</script>

<Modal title="Exportar para QGIS" onclose={() => (app.modal = null)}>
	<div class="fmts">
		{#each FORMATS as f}
			<label class="fmt" class:on={fmt === f.id}>
				<input type="radio" name="fmt" value={f.id} bind:group={fmt} />
				<span class="ic"><Icon name={f.icon} /></span>
				<span><b>{f.name}</b><small>{f.desc}</small></span>
			</label>
		{/each}
	</div>
	{#if fmt === 'geojson' || fmt === 'csv'}
		<div>
			<h3>Escenarios</h3>
			<div class="row">
				{#each scenarios as s}
					<label class="chip"><input type="checkbox" bind:checked={chosen[s.id]} /> {s.name_es}</label>
				{/each}
			</div>
		</div>
	{/if}
	{#if fmt !== 'csv' && fmt !== 'pdf'}
		<label class="chip"><input type="checkbox" bind:checked={zones} /> Incluir zonas 2050 ({app.future === 'ssp585_2050' ? 'emisiones altas' : 'moderadas'})</label>
	{/if}
	<p class="muted">{app.province ? `Solo ${app.province}.` : 'Todo el país.'} Proyección WGS 84 (EPSG:4326).</p>
	<div class="row">
		<button class="btn primary" onclick={run} disabled={busy}><Icon name={fmt === 'pdf' ? 'print' : 'download'} size={16} />{busy ? 'Preparando…' : fmt === 'pdf' ? 'Imprimir / guardar PDF' : 'Descargar'}</button>
		{#if msg}<small class="tag-ok">{msg}</small>{/if}
		{#if err}<small class="tag-bad">{err}</small>{/if}
	</div>
</Modal>

<style>
	.fmts { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
	.fmt { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.7rem; border: 1px solid var(--line); border-radius: 12px; cursor: pointer; }
	.fmt input { position: absolute; opacity: 0; }
	.fmt.on { border-color: var(--accent); background: var(--accent-soft); }
	.fmt span:last-child { display: flex; flex-direction: column; gap: 0.15rem; }
	.fmt small { color: var(--ink-2); font-size: 0.78rem; }
	.ic { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; background: var(--surface-2); color: var(--accent); flex-shrink: 0; }
	h3 { margin-bottom: 0.4rem; }
	.chip { display: inline-flex; gap: 0.35rem; align-items: center; padding: 0.3rem 0.65rem; border: 1px solid var(--line); border-radius: 999px; font-size: 0.85rem; cursor: pointer; }
	.chip input { accent-color: var(--accent); }
	@media (max-width: 560px) { .fmts { grid-template-columns: 1fr; } }
</style>
