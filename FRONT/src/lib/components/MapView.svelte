<script lang="ts">
	import * as maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { RISK_COLORS, RISK_LABEL, ZONE_COLORS, ZONE_LABEL, PATHOGEN_LABEL, pct, usd, errMsg } from '#lib/fmt';
	import Segmented from './Segmented.svelte';

	let el: HTMLDivElement;
	let map: maplibregl.Map | null = null;
	// Se incrementa en cada carga de estilo (también al cambiar de tema): los $effect re-aplican datos.
	let styleTick = $state(0);
	let appliedTheme = app.theme;
	let error = $state('');
	let loading = $state(false);
	let classes = $state<{ id: string; max: number }[]>([]);
	let zoneLegend = $state<Record<string, string>>({});
	let locating = $state(false);

	const STYLES = {
		light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
		dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
	};
	const empty: any = { type: 'FeatureCollection', features: [] };

	const riskExpr: any = ['match', ['get', 'risk_class'], ...Object.entries(RISK_COLORS).flat(), '#bbb'];
	const zoneExpr: any = ['match', ['get', 'zone_class'], ...Object.entries(ZONE_COLORS).flat(), '#bbb'];

	onMount(() => {
		map = new maplibregl.Map({ container: el, style: STYLES[app.theme], center: [-79.6, -1.3], zoom: 6.4, attributionControl: { compact: true } });
		map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
		map.on('style.load', () => {
			const m = map!, dark = appliedTheme === 'dark';
			m.addSource('areas', { type: 'geojson', data: empty, promoteId: 'id' });
			m.addSource('obs', { type: 'geojson', data: empty });
			m.addLayer({ id: 'fill', type: 'fill', source: 'areas', paint: { 'fill-color': riskExpr, 'fill-opacity': 0.72, 'fill-opacity-transition': { duration: 450 } } });
			m.addLayer({ id: 'line', type: 'line', source: 'areas', paint: { 'line-color': dark ? '#0f1712' : '#ffffff', 'line-width': 1 } });
			m.addLayer({ id: 'sel', type: 'line', source: 'areas', filter: ['==', ['get', 'id'], ''], paint: { 'line-color': dark ? '#e4ece5' : '#1f2a22', 'line-width': 2.5 } });
			m.addLayer({ id: 'obs', type: 'circle', source: 'obs', paint: { 'circle-radius': 4, 'circle-color': dark ? '#e4ece5' : '#1f2a22', 'circle-stroke-color': dark ? '#0f1712' : '#fff', 'circle-stroke-width': 1.5, 'circle-opacity': 0.85 } });
			styleTick++;
		});
		map.on('load', () => {
			const m = map!;
			const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
			m.on('mousemove', 'fill', (e) => {
				m.getCanvas().style.cursor = 'pointer';
				const p: any = e.features?.[0]?.properties ?? {};
				const body = app.mapMode === 'loss'
					? `<b>${p.name}</b><br>Pérdida ${pct(p.loss_pct)} · ${usd(p.loss_usd)}<br><small>${RISK_LABEL[p.risk_class] ?? ''}</small>`
					: `<b>${p.name}</b><br>${ZONE_LABEL[p.zone_class] ?? 'Sin datos'}<br><small>Aptitud ${fmt2(p.suitability_now)} → ${fmt2(p.suitability_future)}</small>`;
				pop.setLngLat(e.lngLat).setHTML(body).addTo(m);
			});
			m.on('mouseleave', 'fill', () => { m.getCanvas().style.cursor = ''; pop.remove(); });
			m.on('mousemove', 'obs', (e) => {
				const p: any = e.features?.[0]?.properties ?? {};
				pop.setLngLat(e.lngLat).setHTML(`<b>${PATHOGEN_LABEL[p.pathogen_id] ?? 'Observación'}</b><br>${p.observed_on} · ${p.source}`).addTo(m);
			});
			m.on('click', (e) => {
				const f = m.queryRenderedFeatures(e.point, { layers: ['fill'] })[0];
				if (f) app.select(String(f.properties!.id), String(f.properties!.name));
				else app.selectPoint(+e.lngLat.lat.toFixed(4), +e.lngLat.lng.toFixed(4)); // fuera de cantones → NASA POWER
			});
		});
		return () => map?.remove();
	});

	const fmt2 = (v: any) => (v == null || v === 'null' ? '—' : Number(v).toFixed(2));

	let fitted = '';
	function fit(fc: any, key: string) {
		if (fitted === key || !fc.features.length) return;
		const b = new maplibregl.LngLatBounds();
		const walk = (c: any) => (typeof c[0] === 'number' ? b.extend(c as [number, number]) : c.forEach(walk));
		fc.features.forEach((f: any) => walk(f.geometry.coordinates));
		map!.fitBounds(b, { padding: { top: 90, bottom: 60, left: window.innerWidth > 900 ? 380 : 30, right: app.selectedId ? 460 : 60 }, duration: 700 });
		fitted = key;
	}

	// Cambio de tema → cambiar mapa base (style.load vuelve a crear las capas)
	$effect(() => {
		const t = app.theme;
		if (!map || t === appliedTheme) return;
		appliedTheme = t;
		map.setStyle(STYLES[t]);
	});

	// Capa principal: pérdidas (/losses/geojson) o zonas 2050 (/areas/geojson + /zones)
	$effect(() => {
		const { mapMode, scenario, province, crop, future } = app;
		void app.refresh;
		if (!styleTick) return;
		let cancelled = false;
		loading = true; error = '';
		map!.setPaintProperty('fill', 'fill-opacity', 0.2);
		const job = mapMode === 'loss'
			? api.lossesGeojson({ scenario, province: province || undefined, crop }).then((fc: any) => { classes = fc.classes ?? []; return fc; })
			: Promise.all([api.areasGeojson({ province: province || undefined }), api.zones(future, crop, province || undefined)]).then(([fc, z]: any) => {
					zoneLegend = z.legend ?? {};
					const byId = new Map(z.items.map((i: any) => [i.area_id, i]));
					fc.features.forEach((f: any) => Object.assign(f.properties, byId.get(f.properties.id) ?? {}));
					return fc;
				});
		job.then((fc) => {
			if (cancelled) return;
			(map!.getSource('areas') as maplibregl.GeoJSONSource).setData(fc);
			map!.setPaintProperty('fill', 'fill-color', mapMode === 'loss' ? riskExpr : zoneExpr);
			map!.setPaintProperty('fill', 'fill-opacity', 0.72);
			fit(fc, province);
		}).catch((e) => !cancelled && (error = errMsg(e))).finally(() => !cancelled && (loading = false));
		return () => { cancelled = true; };
	});

	// Observaciones de campo (/observations)
	$effect(() => {
		const show = app.showObservations;
		void app.refresh;
		if (!styleTick) return;
		map!.setLayoutProperty('obs', 'visibility', show ? 'visible' : 'none');
		if (!show) return;
		api.observations({ limit: 1000 }).then((rows) => {
			const fc: any = {
				type: 'FeatureCollection',
				features: rows.filter((r) => r.lat != null).map((r) => ({ type: 'Feature', properties: r, geometry: { type: 'Point', coordinates: [r.lon, r.lat] } }))
			};
			(map!.getSource('obs') as maplibregl.GeoJSONSource).setData(fc);
		}).catch(() => {});
	});

	// Resaltar selección y marcador de punto libre
	let marker: maplibregl.Marker | null = null;
	$effect(() => {
		if (!styleTick) return;
		map!.setFilter('sel', ['==', ['get', 'id'], app.selectedId ?? '']);
		marker?.remove(); marker = null;
		if (app.point) marker = new maplibregl.Marker({ color: '#5a3a22' }).setLngLat([app.point.lon, app.point.lat]).addTo(map!);
	});

	// "Mi finca": geolocalización → /areas/lookup
	function locate() {
		if (!navigator.geolocation) return;
		locating = true;
		navigator.geolocation.getCurrentPosition(async ({ coords }) => {
			const lat = +coords.latitude.toFixed(4), lon = +coords.longitude.toFixed(4);
			map?.flyTo({ center: [lon, lat], zoom: 9 });
			try {
				const r: any = await api.lookup(lat, lon);
				app.select(r.canton.id, r.canton.name);
			} catch {
				app.selectPoint(lat, lon);
			} finally { locating = false; }
		}, () => (locating = false), { timeout: 10000 });
	}

	const modeOpts = [{ id: 'loss', label: 'Pérdidas' }, { id: 'zones', label: 'Zonas 2050' }];
	const futureOpts = [{ id: 'ssp245_2050', label: 'Moderado' }, { id: 'ssp585_2050', label: 'Alto' }];
</script>

<div class="wrap" class:panel={app.selectedId || app.point}>
	<div bind:this={el} class="map"></div>

	<div class="controls card">
		<Segmented options={modeOpts} bind:value={app.mapMode} size="sm" />
		{#if app.mapMode === 'zones'}
			<div class="row"><small>Emisiones</small><Segmented options={futureOpts} bind:value={app.future} size="sm" /></div>
		{/if}
		<div class="legend">
			{#if app.mapMode === 'loss'}
				{#each classes as c, i}
					<span><i style="background:{RISK_COLORS[c.id]}"></i>{RISK_LABEL[c.id] ?? c.id} <small>{i ? `${classes[i - 1].max}–` : '< '}{c.max} %</small></span>
				{/each}
			{:else}
				{#each Object.entries(ZONE_COLORS) as [k, c]}
					<span title={zoneLegend[k]}><i style="background:{c}"></i>{ZONE_LABEL[k]}</span>
				{/each}
			{/if}
		</div>
		<div class="row">
			<label class="chk"><input type="checkbox" bind:checked={app.showObservations} /> Observaciones de campo</label>
		</div>
		<button class="btn sm" onclick={locate} disabled={locating}>{locating ? 'Ubicando…' : '◎ Mi finca'}</button>
		{#if loading}<small>Cargando mapa…</small>{/if}
		{#if error}<small class="tag-bad">{error}</small>{/if}
	</div>
	<p class="hint">Toca un cantón para ver su detalle · toca fuera para consultar el clima del punto (NASA POWER)</p>
</div>

<style>
	.wrap { position: absolute; inset: 0; }
	.map { position: absolute; inset: 0; }
	.wrap :global(.maplibregl-ctrl-bottom-right) { transition: right 0.25s; }
	.wrap.panel :global(.maplibregl-ctrl-bottom-right) { right: 470px; }
	.controls {
		position: absolute; left: 20px; bottom: 28px; z-index: 2;
		display: flex; flex-direction: column; gap: 0.65rem; align-items: flex-start;
		box-shadow: var(--shadow); max-width: 260px; padding: 0.9rem; border-top: 4px solid var(--accent);
	}
	.legend { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.82rem; }
	.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 0.45rem; vertical-align: -1px; }
	.legend small { margin-left: 0.2rem; }
	.chk { display: flex; gap: 0.4rem; align-items: center; font-size: 0.82rem; cursor: pointer; }
	.hint { position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%); margin: 0; font-size: 0.75rem; color: var(--ink-2); background: color-mix(in srgb, var(--surface) 85%, transparent); padding: 0.2rem 0.7rem; border-radius: 999px; white-space: nowrap; pointer-events: none; }
	@media (max-width: 900px) {
		.controls { left: 12px; bottom: auto; top: 12px; max-width: 200px; padding: 0.7rem; }
		.hint { display: none; }
		.wrap.panel :global(.maplibregl-ctrl-bottom-right) { right: 0; bottom: 68vh; }
	}
</style>
