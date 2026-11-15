<script lang="ts">
	import * as maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { onMount } from 'svelte';
	import { api } from '#lib/api';
	import { app } from '#lib/state.svelte';
	import { LOSS_RAMP, LOSS_CLASSES, lossLabel, ZONE_COLORS, ZONE_LABEL, PATHOGEN_LABEL, pct, usd, errMsg } from '#lib/fmt';
	import Segmented from './Segmented.svelte';
	import Icon from './Icon.svelte';
	import { style3d, resolveOverlay, DEM_SOURCE, cacaoIcon, haversineKm, BASES, OVERLAYS, type BaseId } from '#lib/basemaps';
	import { ringAreaHa, ringCentroid, selfIntersects, type LonLat } from '#lib/geo';
	import type { OverlayId } from '#lib/state.svelte';

	let el: HTMLDivElement;
	let map: maplibregl.Map | null = null;
	// Se incrementa en cada carga de estilo (también al cambiar de tema): los $effect re-aplican datos.
	let styleTick = $state(0);
	const styleKey = () => (app.view === '3d' ? `3d|${app.base3d}` : `2d|${app.base2d}|${app.base2d === 'tema' ? app.theme : ''}`);
	let appliedKey = styleKey();
	let is3d = app.view === '3d';
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

	// Pérdida: 5 niveles por % (límite superior inclusivo, igual que FRONT y QGIS). Sin dato → gris neutro.
	const NODATA = '#8a948c';
	const riskExpr: any = ['case', ['==', ['typeof', ['get', 'loss_pct']], 'number'],
		['step', ['get', 'loss_pct'], LOSS_RAMP[0], 5.0001, LOSS_RAMP[1], 15.0001, LOSS_RAMP[2], 30.0001, LOSS_RAMP[3], 45.0001, LOSS_RAMP[4]],
		NODATA];
	const zoneExpr: any = ['match', ['get', 'zone_class'], ...Object.entries(ZONE_COLORS).flat(), NODATA];

	// Colores del mapa base por tema: agua y fondo con la paleta, para que los datos resalten
	const BASE = {
		light: { bg: '#eef1ec', water: '#b9dccd', line: '#4b3a2f', lineOp: 0.45, sel: '#2b221c', obs: '#2b221c', obsStroke: '#ffffff' },
		dark: { bg: '#1c2721', water: '#163033', line: '#eceff1', lineOp: 0.35, sel: '#ffffff', obs: '#eceff1', obsStroke: '#18231d' }
	};
	function tintBasemap(m: maplibregl.Map, t: (typeof BASE)['light']) {
		for (const l of m.getStyle().layers ?? []) {
			try {
				if (l.type === 'background') m.setPaintProperty(l.id, 'background-color', t.bg);
				else if (l.type === 'fill' && /water|ocean|sea|lake/.test(l.id)) m.setPaintProperty(l.id, 'fill-color', t.water);
				else if (l.type === 'fill' && /landcover|landuse|park|wood|grass/.test(l.id)) m.setPaintProperty(l.id, 'fill-opacity', 0.25);
			} catch { /* capa sin esa propiedad */ }
		}
	}

	const styleFor = () => (app.view === '3d' ? style3d(app.base3d) : app.base2d === 'tema' ? STYLES[app.theme] : style3d(app.base2d));
	const curBase = () => (app.view === '3d' ? app.base3d : app.base2d);
	const fillOp = () => (is3d ? 0.6 : 0.82);

	onMount(() => {
		map = new maplibregl.Map({ container: el, style: styleFor(), center: [-79.6, -1.3], zoom: 6.4, attributionControl: { compact: true }, maxPitch: 75 });
		map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-right');
		map.on('style.load', () => {
			const m = map!, dark = app.theme === 'dark';
			is3d = app.view === '3d';
			// En satélite: bordes claros y relleno más transparente para ver el terreno debajo
			const t = is3d ? { ...BASE.dark, line: '#ffffff', lineOp: 0.55 } : BASE[dark ? 'dark' : 'light'];
			if (is3d) {
				if (!m.getSource('dem')) m.addSource('dem', DEM_SOURCE as any);
				for (const z of Object.keys(ZONE_COLORS)) if (!m.hasImage(`cacao-${z}`)) m.addImage(`cacao-${z}`, cacaoIcon(ZONE_COLORS[z]), { pixelRatio: 2 });
				apply3d();
				if (m.getPitch() < 10) m.easeTo({ pitch: 58, bearing: -12, duration: 900 });
			} else {
				m.setProjection({ type: 'mercator' });
				m.setTerrain(null);
				if (app.base2d === 'tema') tintBasemap(m, t);
				else { if (!m.getSource('dem')) m.addSource('dem', DEM_SOURCE as any); apply2d(); }
				for (const z of Object.keys(ZONE_COLORS)) if (!m.hasImage(`cacao-${z}`)) m.addImage(`cacao-${z}`, cacaoIcon(ZONE_COLORS[z]), { pixelRatio: 2 });
				if (m.getPitch() > 0) m.easeTo({ pitch: 0, bearing: 0, duration: 600 });
			}
			// Datos debajo de los nombres: en ráster la capa 'labels'; en vectorial, el primer símbolo
			const before = m.getLayer('labels') ? 'labels' : is3d || app.base2d !== 'tema' ? m.getStyle().layers.find((l) => l.type === 'symbol')?.id : undefined;
			// En 2D con fondo de satélite u oscuro: bordes claros como en 3D
			if (!is3d && app.base2d !== 'tema' && app.base2d !== 'predeterminado') Object.assign(t, { line: '#ffffff', lineOp: 0.55, sel: '#ffffff' });
			m.addSource('areas', { type: 'geojson', data: empty, promoteId: 'id' });
			m.addSource('obs', { type: 'geojson', data: empty });
			m.addSource('draft', { type: 'geojson', data: empty });
			m.addSource('cacao', { type: 'geojson', data: empty });
			m.addSource('prov', { type: 'geojson', data: provFc ?? empty });
			m.addSource('prov3d', { type: 'geojson', data: prov3dFc ?? empty });
			m.addSource('prov3d-edge', { type: 'geojson', data: prov3dEdge ?? empty });
			m.addSource('medida', { type: 'geojson', data: empty });
			m.addSource('finca', { type: 'geojson', data: empty });
			m.addLayer({ id: 'fill', type: 'fill', source: 'areas', paint: { 'fill-color': riskExpr, 'fill-opacity': fillOp(), 'fill-opacity-transition': { duration: 450 } } }, before);
			m.addLayer({ id: 'line', type: 'line', source: 'areas', paint: { 'line-color': t.line, 'line-opacity': t.lineOp, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 9, 1.4] } }, before);
			// Provincias: halo + borde, encima de los cantones (en 3D se ven sobre el relieve)
			m.addLayer({ id: 'prov-halo', type: 'line', source: 'prov', layout: { 'line-join': 'round' }, paint: { 'line-color': is3d ? '#000000' : dark ? '#101512' : '#ffffff', 'line-opacity': is3d ? 0.45 : 0.6, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 3, 9, 6] } }, before);
			m.addLayer({ id: 'prov-line', type: 'line', source: 'prov', layout: { 'line-join': 'round' }, paint: { 'line-color': is3d ? '#f3ecd8' : dark ? '#dfe4dc' : '#4b3a2f', 'line-opacity': 0.95, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 1.3, 9, 2.6] } }, before);
			// Provincias en 3D: bloque con la forma real de la provincia; altura y color según la pérdida
			// Borde: bloque oscuro con la forma completa; encima, el bloque de color un poco más adentro y más alto.
			// Así cada provincia muestra una línea en el canto superior y paredes marcadas.
			m.addLayer({ id: 'prov-ext-edge', type: 'fill-extrusion', source: 'prov3d-edge', layout: { visibility: app.prov3d ? 'visible' : 'none' },
				paint: {
					'fill-extrusion-color': is3d || dark ? '#f3ecd8' : '#2b221c',
					'fill-extrusion-height': ['*', ['coalesce', ['get', 'loss_pct'], 0.5], 2000],
					'fill-extrusion-base': 0,
					'fill-extrusion-opacity': 0.92,
					'fill-extrusion-height-transition': { duration: 700 }
				} });
			m.addLayer({ id: 'prov-ext', type: 'fill-extrusion', source: 'prov3d', layout: { visibility: app.prov3d ? 'visible' : 'none' },
				paint: {
					'fill-extrusion-color': ['case', ['==', ['typeof', ['get', 'loss_pct']], 'number'],
						['step', ['get', 'loss_pct'], LOSS_RAMP[0], 5.0001, LOSS_RAMP[1], 15.0001, LOSS_RAMP[2], 30.0001, LOSS_RAMP[3], 45.0001, LOSS_RAMP[4]], NODATA],
					'fill-extrusion-height': ['+', ['*', ['coalesce', ['get', 'loss_pct'], 0.5], 2000], 600],
					'fill-extrusion-base': 0,
					'fill-extrusion-opacity': 0.95,
					'fill-extrusion-height-transition': { duration: 700 }
				} });
			m.addLayer({ id: 'sel', type: 'line', source: 'areas', filter: ['==', ['get', 'id'], ''], paint: { 'line-color': t.sel, 'line-width': 3 } }, before);
			m.addLayer({ id: 'obs', type: 'circle', source: 'obs', paint: { 'circle-radius': 4, 'circle-color': t.obs, 'circle-stroke-color': t.obsStroke, 'circle-stroke-width': 1.5, 'circle-opacity': 0.85 } });
			// Mi finca: borrador mientras se dibuja y la finca terminada
			m.addLayer({ id: 'finca-fill', type: 'fill', source: 'finca', paint: { 'fill-color': '#96c9b2', 'fill-opacity': 0.35 } });
			m.addLayer({ id: 'finca-line', type: 'line', source: 'finca', paint: { 'line-color': '#3d5a43', 'line-width': 3 } });
			m.addLayer({ id: 'draft-line', type: 'line', source: 'draft', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#c9bd7e', 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
			m.addLayer({ id: 'medida-linea', type: 'line', source: 'medida', paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-dasharray': [2, 1.5] } });
			m.addLayer({ id: 'medida-pts', type: 'circle', source: 'medida', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 5, 'circle-color': '#96c9b2', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 } });
			m.addLayer({ id: 'cacao', type: 'symbol', source: 'cacao', layout: { 'icon-image': ['get', 'icon'], 'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.45, 9, 0.8], 'icon-allow-overlap': true, visibility: app.cacaoIcons ? 'visible' : 'none' } });
			cacaoKey = '';
			m.addLayer({ id: 'draft-pts', type: 'circle', source: 'draft', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 5, 'circle-color': '#c9bd7e', 'circle-stroke-color': '#2b221c', 'circle-stroke-width': 2 } });
			ovlKey = '';
			styleTick++;
		});
		map.on('load', () => {
			const m = map!;
			const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
			m.on('mousemove', 'fill', (e) => {
				m.getCanvas().style.cursor = 'pointer';
				const p: any = e.features?.[0]?.properties ?? {};
				const body = app.mapMode === 'loss'
					? `<b>${p.name}</b><br>Pérdida ${pct(p.loss_pct === 'null' ? null : p.loss_pct)}${p.loss_usd != null && p.loss_usd !== 'null' ? ' · ' + usd(Number(p.loss_usd)) : ''}<br><small>${lossLabel(p.loss_pct == null || p.loss_pct === 'null' ? null : Number(p.loss_pct))}${p.inherited_from && p.inherited_from !== 'null' ? ' · índice de ' + p.inherited_from : ''}</small>`
					: `<b>${p.name}</b><br>${ZONE_LABEL[p.zone_class] ?? 'Sin datos'}<br><small>Aptitud ${fmt2(p.suitability_now)} → ${fmt2(p.suitability_future)}</small>`;
				pop.setLngLat(e.lngLat).setHTML(body).addTo(m);
			});
			m.on('mouseleave', 'fill', () => { m.getCanvas().style.cursor = ''; pop.remove(); });
			m.on('mousemove', 'prov-ext', (e) => {
				if (!app.prov3d) return;
				const p: any = e.features?.[0]?.properties ?? {};
				const v = p.loss_pct == null || p.loss_pct === 'null' ? null : Number(p.loss_pct);
				pop.setLngLat(e.lngLat).setHTML(`<b>${p.name}</b><br>Pérdida ${pct(v)}${p.loss_usd && p.loss_usd !== 'null' ? ' · ' + usd(Number(p.loss_usd)) : ''}<br><small>${lossLabel(v)} · provincia</small>`).addTo(m);
			});
			m.on('mouseleave', 'prov-ext', () => pop.remove());
			m.on('mousemove', 'obs', (e) => {
				const p: any = e.features?.[0]?.properties ?? {};
				pop.setLngLat(e.lngLat).setHTML(`<b>${PATHOGEN_LABEL[p.pathogen_id] ?? 'Observación'}</b><br>${p.observed_on} · ${p.source}`).addTo(m);
			});
			m.on('click', (e) => {
				if (app.fincaMode) { app.draft = [...app.draft, [+e.lngLat.lng.toFixed(6), +e.lngLat.lat.toFixed(6)]]; return; }
				if (app.measuring) { app.measure = [...app.measure, [+e.lngLat.lng.toFixed(6), +e.lngLat.lat.toFixed(6)]]; return; }
				const c = m.getLayer('cacao') ? m.queryRenderedFeatures(e.point, { layers: ['cacao'] })[0] : null;
				if (c) { app.select(String(c.properties!.id), String(c.properties!.name)); return; }
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

	// Cambio de tema, de vista 2D/3D o de tipo de mapa 3D → cambiar mapa base (style.load vuelve a crear las capas)
	$effect(() => {
		const k = styleKey();
		if (!map || k === appliedKey) return;
		appliedKey = k;
		map.setTerrain(null);
		map.setStyle(styleFor());
	});

	// Opciones del 3D que no recargan el estilo: globo, relieve y nombres
	function apply3d() {
		const m = map;
		if (!m || app.view !== '3d') return;
		m.setProjection({ type: app.globe ? 'globe' : 'mercator' });
		m.setTerrain(app.terrain && m.getSource('dem') ? { source: 'dem', exaggeration: 1.6 } : null);
		if (m.getLayer('relieve')) m.setLayoutProperty('relieve', 'visibility', app.terrain || app.base3d === 'hidrografico' ? 'visible' : 'none');
		if (m.getLayer('labels')) m.setLayoutProperty('labels', 'visibility', app.labels ? 'visible' : 'none');
		else for (const l of m.getStyle().layers ?? []) if (l.type === 'symbol' && l.id !== 'cacao') m.setLayoutProperty(l.id, 'visibility', app.labels ? 'visible' : 'none');
	}
	/** 2D con un tipo de mapa: sin relieve 3D, pero con sombreado y nombres a elección */
	function apply2d() {
		const m = map;
		if (!m || app.view !== '2d' || app.base2d === 'tema') return;
		if (m.getLayer('relieve')) m.setLayoutProperty('relieve', 'visibility', app.terrain || app.base2d === 'hidrografico' ? 'visible' : 'none');
		if (m.getLayer('labels')) m.setLayoutProperty('labels', 'visibility', app.labels ? 'visible' : 'none');
		else for (const l of m.getStyle().layers ?? []) if (l.type === 'symbol' && l.id !== 'cacao') m.setLayoutProperty(l.id, 'visibility', app.labels ? 'visible' : 'none');
	}
	$effect(() => {
		void app.globe; void app.terrain; void app.labels;
		if (!styleTick) return;
		apply3d(); apply2d();
	});

	// Mazorcas en los cantones aptos para cacao en 2050 (zonas Segura y Manejo), solo en 3D
	let cacaoKey = '';
	let nApt = $state(0);
	$effect(() => {
		void app.prov3d;
		const on = app.cacaoIcons, fut = app.future, crop = app.crop, prov = app.province;
		if (!styleTick || !map || !map.getLayer('cacao')) return;
		map.setLayoutProperty('cacao', 'visibility', on && !app.prov3d ? 'visible' : 'none');
		const key = `${fut}|${crop}|${prov}`;
		if (!on || key === cacaoKey) return;
		cacaoKey = key;
		Promise.all([api.areasGeojson({ province: prov || undefined }), api.zones(fut, crop, prov || undefined)]).then(([fc, z]: any) => {
			const by = new Map(z.items.map((i: any) => [i.area_id, i]));
			const pts = fc.features.flatMap((f: any) => {
				const zi: any = by.get(f.properties.id);
				if (!zi || !['segura', 'manejo'].includes(zi.zone_class)) return [];
				return [{ type: 'Feature', properties: { id: f.properties.id, name: f.properties.name, icon: `cacao-${zi.zone_class}` }, geometry: { type: 'Point', coordinates: labelPoint(f.geometry) } }];
			});
			nApt = pts.length;
			(map?.getSource('cacao') as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features: pts } as any);
		}).catch(() => {});
	});
	/** Punto para el ícono: centroide del anillo exterior más grande */
	function labelPoint(g: any): [number, number] {
		const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
		let best = polys[0][0], bestN = 0;
		for (const p of polys) if (p[0].length > bestN) { best = p[0]; bestN = p[0].length; }
		return ringCentroid(best.slice(0, -1) as LonLat[]);
	}

	// Herramienta Medir: distancia de la línea y área si se cierra en 3 o más puntos
	$effect(() => {
		const pts = app.measure, on = app.measuring;
		if (!styleTick || !map) return;
		const feats: any[] = pts.map((p) => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: p } }));
		if (pts.length > 1) feats.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: pts } });
		(map.getSource('medida') as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features: on ? feats : [] } as any);
		if (on) map.getCanvas().style.cursor = 'crosshair';
	});
	const distKm = $derived(app.measure.slice(1).reduce((s, p, i) => s + haversineKm(app.measure[i] as [number, number], p as [number, number]), 0));
	const measHa = $derived(app.measure.length > 2 ? ringAreaHa(app.measure as LonLat[]) : 0);
	let layersOpen = $state(false);
	const OVL = Object.entries(OVERLAYS) as [OverlayId, (typeof OVERLAYS)[OverlayId]][];
	const fmtKm = (k: number) => (k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`);
	const fmtHa = (h: number) => (h < 100 ? `${h.toFixed(1)} ha` : `${Math.round(h).toLocaleString('es-EC')} ha`);

	// Capas NASA del día (GIBS) debajo del relleno de datos
	let ovlKey = '';
	$effect(() => {
		const on = (Object.keys(app.overlays) as OverlayId[]).filter((k) => app.overlays[k]);
		if (!styleTick || !map) return;
		const key = on.join(',');
		if (key === ovlKey) return;
		ovlKey = key;
		const m = map;
		for (const l of m.getStyle().layers ?? []) if (l.id.startsWith('ovl-')) m.removeLayer(l.id);
		for (const sid of Object.keys(m.getStyle().sources ?? {})) if (sid.startsWith('ovl-')) m.removeSource(sid);
		on.forEach(async (id) => {
			const src = await resolveOverlay(id);
			if (!src || !map || ovlKey !== key) return;
			src.urls.forEach((u, i) => {
				const sid = `ovl-${id}-${i}`;
				if (m.getSource(sid)) return;
				m.addSource(sid, { type: 'raster', tiles: [u], tileSize: 256, maxzoom: src.maxzoom, attribution: i ? undefined : src.attribution });
				m.addLayer({ id: sid, type: 'raster', source: sid, paint: { 'raster-opacity': src.opacity } }, 'fill');
			});
		});
	});

	// Mi finca: dibujar el borrador y la finca terminada
	$effect(() => {
		const pts = app.draft, f = app.finca;
		if (!styleTick || !map) return;
		const feats: any[] = pts.map((p) => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: p } }));
		if (pts.length > 1) feats.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: pts.length > 2 ? [...pts, pts[0]] : pts } });
		(map.getSource('draft') as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features: app.fincaMode ? feats : [] } as any);
		(map.getSource('finca') as maplibregl.GeoJSONSource)?.setData(f ? { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[...f.points, f.points[0]]] } } as any : empty);
		map.getCanvas().style.cursor = app.fincaMode || app.measuring ? 'crosshair' : '';
	});

	// Límites de provincias (se cargan una vez)
	let provFc: any = null;
	$effect(() => {
		if (!styleTick || !map) return;
		if (provFc) { (map.getSource('prov') as maplibregl.GeoJSONSource)?.setData(provFc); return; }
		api.areasGeojson({ kind: 'province' }).then((fc: any) => { provFc = fc; (map?.getSource('prov') as maplibregl.GeoJSONSource)?.setData(fc); }).catch(() => {});
	});

	// Provincias en 3D: une los límites con la pérdida por provincia del escenario elegido
	let prov3dFc: any = null;
	let prov3dEdge: any = null;
	/** Encoge cada parte del polígono hacia su centro (para dejar ver el borde oscuro de debajo) */
	function inset(g: any, f = 0.972): any {
		const shrink = (poly: number[][][]) => {
			const [cx, cy] = ringCentroid(poly[0].slice(0, -1) as LonLat[]);
			return poly.map((r) => r.map(([x, y]) => [cx + (x - cx) * f, cy + (y - cy) * f]));
		};
		return g.type === 'Polygon' ? { type: 'Polygon', coordinates: shrink(g.coordinates) } : { type: 'MultiPolygon', coordinates: g.coordinates.map(shrink) };
	}
	$effect(() => {
		const on = app.prov3d, sc = app.scenario, crop = app.crop;
		if (!styleTick || !map || !map.getLayer('prov-ext')) return;
		map.setLayoutProperty('prov-ext', 'visibility', on ? 'visible' : 'none');
		map.setLayoutProperty('prov-ext-edge', 'visibility', on ? 'visible' : 'none');
		// Con el relieve de provincias los cantones se ven más tenues para no competir
		map.setPaintProperty('fill', 'fill-opacity', on ? 0.25 : fillOp());
		if (!on) return;
		if (map.getPitch() < 30) map.easeTo({ pitch: 55, bearing: -15, duration: 900 });
		Promise.all([provFc ? Promise.resolve(provFc) : api.areasGeojson({ kind: 'province' }), api.losses({ scenario: sc, kind: 'province', crop })]).then(([fc, l]: any[]) => {
			provFc = fc;
			const by = new Map(l.items.map((i: any) => [i.area_id, i]));
			const withLoss = fc.features.map((f: any) => {
				const i: any = by.get(f.properties.id);
				return { ...f, properties: { ...f.properties, loss_pct: i?.loss_pct ?? null, loss_usd: i?.loss_usd ?? null } };
			});
			prov3dEdge = { type: 'FeatureCollection', features: withLoss };
			prov3dFc = { type: 'FeatureCollection', features: withLoss.map((f: any) => ({ ...f, geometry: inset(f.geometry) })) };
			(map?.getSource('prov3d-edge') as maplibregl.GeoJSONSource)?.setData(prov3dEdge);
			(map?.getSource('prov3d') as maplibregl.GeoJSONSource)?.setData(prov3dFc);
		}).catch(() => {});
	});

	const draftHa = $derived(app.draft.length > 2 ? ringAreaHa(app.draft as LonLat[]) : 0);
	const draftBad = $derived(app.draft.length > 3 && selfIntersects(app.draft as LonLat[]));
	let fincaMsg = $state('');
	async function finishFinca() {
		const pts = app.draft as LonLat[];
		const [lon, lat] = ringCentroid(pts);
		let cantonId: string | null = null, cantonName = '';
		try { const r: any = await api.lookup(+lat.toFixed(5), +lon.toFixed(5)); cantonId = r.canton?.id ?? null; cantonName = r.canton?.name ?? ''; } catch { /* fuera de cantones */ }
		app.fincaMode = false;
		app.finca = { points: pts, ha: ringAreaHa(pts), center: [lon, lat], cantonId, cantonName };
		app.draft = [];
		app.tab = 'resumen';
	}
	function gpsPoint() {
		fincaMsg = '';
		navigator.geolocation?.getCurrentPosition(({ coords }) => {
			const p: [number, number] = [+coords.longitude.toFixed(6), +coords.latitude.toFixed(6)];
			app.draft = [...app.draft, p];
			map?.flyTo({ center: p, zoom: Math.max(map.getZoom(), 15) });
		}, () => (fincaMsg = 'No se pudo leer el GPS'), { enableHighAccuracy: true, timeout: 10000 });
	}

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
			map!.setPaintProperty('fill', 'fill-opacity', app.prov3d ? 0.25 : fillOp());
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
		if (app.point) marker = new maplibregl.Marker({ color: '#4b3a2f' }).setLngLat([app.point.lon, app.point.lat]).addTo(map!);
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
	const viewOpts = [{ id: '2d', label: 'Mapa 2D' }, { id: '3d', label: 'Satélite 3D' }];
	const futureOpts = [{ id: 'ssp245_2050', label: 'Moderado' }, { id: 'ssp585_2050', label: 'Alto' }];
</script>

<div class="wrap" class:panel={app.selectedId || app.point}>
	<div bind:this={el} class="map"></div>

	{#if app.fincaMode}
		<div class="draw card">
			<b><Icon name="farm" size={18} /> Dibuja tu finca</b>
			<small>Toca las esquinas del lote en el mapa{app.draft.length ? ` · ${app.draft.length} punto(s)` : ''}{draftHa ? ` · ${draftHa < 10 ? draftHa.toFixed(2) : draftHa.toFixed(1)} ha` : ''}</small>
			{#if draftBad}<small class="tag-bad">Los lados se cruzan: deshaz el último punto.</small>{/if}
			{#if fincaMsg}<small class="tag-bad">{fincaMsg}</small>{/if}
			<div class="row">
				<button class="btn sm" onclick={gpsPoint}><Icon name="gps" size={16} /> Punto GPS</button>
				<button class="btn sm" onclick={() => (app.draft = app.draft.slice(0, -1))} disabled={!app.draft.length}><Icon name="undo" size={16} /> Deshacer</button>
				<button class="btn sm primary" onclick={finishFinca} disabled={app.draft.length < 3 || draftBad}><Icon name="check" size={16} /> Terminar</button>
				<button class="btn sm" onclick={() => { app.fincaMode = false; app.draft = []; }}>Cancelar</button>
			</div>
		</div>
	{/if}

	{#if true}
		<div class="layers">
			{#if layersOpen}
				<div class="lp card" role="dialog" aria-label="Capas del mapa">
					<div class="spread"><b class="ttl">Tipo de mapa</b><button class="x" onclick={() => (layersOpen = false)} aria-label="Cerrar capas"><Icon name="close" size={16} /></button></div>
					<div class="bases" role="radiogroup" aria-label="Tipo de mapa">
						{#if app.view === '2d'}
							<button role="radio" aria-checked={app.base2d === 'tema'} class:on={app.base2d === 'tema'} title="Claro u oscuro según el tema, con el mar en la paleta" onclick={() => (app.base2d = 'tema')}>
								<span class="th" style="background-image:{app.theme === 'dark' ? 'linear-gradient(135deg,#1c2721 0 55%,#163033 55%)' : 'linear-gradient(135deg,#eef1ec 0 55%,#b9dccd 55%)'}"></span>Según tema
							</button>
						{/if}
						{#each Object.entries(BASES) as [id, b]}
							<button role="radio" aria-checked={curBase() === id} class:on={curBase() === id} title={b.detail} onclick={() => (app.view === '3d' ? (app.base3d = id as BaseId) : (app.base2d = id as BaseId))}>
								<span class="th" style="background-image:{b.thumb}"></span>{b.label}
							</button>
						{/each}
					</div>
					<small class="muted">{curBase() === 'tema' ? 'Mapa claro u oscuro según el tema · CARTO / OpenStreetMap' : BASES[curBase() as BaseId].detail}</small>
					<div class="row">
						{#if app.view === '3d'}<label class="chk"><input type="checkbox" bind:checked={app.globe} /> Vista de globo</label>{/if}
						<label class="chk"><input type="checkbox" bind:checked={app.labels} /> Etiquetas</label>
					</div>
					<b class="ttl">Detalles del mapa</b>
					<div class="bases dets">
						<button aria-pressed={app.terrain} class:on={app.terrain} onclick={() => (app.terrain = !app.terrain)}><span class="th ic"><Icon name="layers" size={22} /></span>{app.view === '3d' ? 'Relieve 3D' : 'Relieve'}</button>
						<button aria-pressed={app.cacaoIcons} class:on={app.cacaoIcons} onclick={() => (app.cacaoIcons = !app.cacaoIcons)} title="Mazorcas en los cantones aptos en 2050 (zonas Segura y Manejo)"><span class="th ic"><Icon name="farm" size={22} /></span>Cacao apto · {nApt}</button>
						<button aria-pressed={app.prov3d} class:on={app.prov3d} onclick={() => (app.prov3d = !app.prov3d)} title="Altura de cada provincia = pérdida estimada"><span class="th ic"><Icon name="dash" size={22} /></span>Provincias 3D</button>
						{#each OVL as [id, o]}
							<button aria-pressed={app.overlays[id]} class:on={app.overlays[id]} onclick={() => (app.overlays[id] = !app.overlays[id])}><span class="th ic"><Icon name="spark" size={22} /></span>{o.label}</button>
						{/each}
					</div>
					<b class="ttl">Herramientas del mapa</b>
					<div class="row">
						<button class="btn sm" class:primary={app.measuring} onclick={() => { app.measuring = !app.measuring; app.measure = []; }}><Icon name="link" size={15} />{app.measuring ? 'Terminar medición' : 'Medir'}</button>
					</div>
				</div>
			{/if}
			<button class="lbtn" onclick={() => (layersOpen = !layersOpen)} aria-expanded={layersOpen} style="background-image:{BASES[curBase() === 'satelite' ? 'predeterminado' : 'satelite'].thumb}">
				<span><Icon name="layers" size={15} /> Capas</span>
			</button>
		</div>
	{/if}

	{#if app.measuring}
		<div class="meas card" role="status">
			{#if app.measure.length < 2}Toca el mapa para medir{:else}Distancia <b>{fmtKm(distKm)}</b>{#if measHa > 0} · Área <b>{fmtHa(measHa)}</b>{/if}{/if}
			{#if app.measure.length}<button class="lnk" onclick={() => (app.measure = [])}>Borrar</button>{/if}
			<button class="lnk" onclick={() => { app.measuring = false; app.measure = []; }}>Listo</button>
		</div>
	{/if}

	<div class="controls card">
		<Segmented options={viewOpts} bind:value={app.view} size="sm" />
		<Segmented options={modeOpts} bind:value={app.mapMode} size="sm" />
		{#if app.mapMode === 'zones'}
			<div class="row"><small>Emisiones</small><Segmented options={futureOpts} bind:value={app.future} size="sm" /></div>
		{/if}
		<div class="legend">
			{#if app.mapMode === 'loss'}
				{#each LOSS_CLASSES as c, i}
					<span><i class:hatch={i === 4} style="background:{LOSS_RAMP[i]}"></i>{c.label} <small>{c.range}</small></span>
				{/each}
				<span><i style="background:{NODATA}"></i>Sin estimación <small>fuera del modelo</small></span>
			{:else}
				{#each Object.entries(ZONE_COLORS) as [k, c]}
					<span title={zoneLegend[k]}><i style="background:{c}"></i>{ZONE_LABEL[k]}</span>
				{/each}
			{/if}
		</div>
		<div class="row">
			<label class="chk"><input type="checkbox" bind:checked={app.showObservations} /> Observaciones de campo</label>
		</div>
		{#if app.mapMode === 'loss'}
			<button class="btn sm p3d" class:primary={app.prov3d} onclick={() => (app.prov3d = !app.prov3d)} aria-pressed={app.prov3d}
				title="Levanta cada provincia según su pérdida estimada">
				<Icon name="layers" size={15} /> {app.prov3d ? 'Quitar provincias 3D' : 'Provincias en 3D'}
			</button>
		{/if}
		<div class="row">
			<button class="btn sm" onclick={locate} disabled={locating}><Icon name="gps" size={15} />{locating ? 'Ubicando…' : 'Ubicarme'}</button>
			<button class="btn sm" onclick={() => app.startFinca()}><Icon name="farm" size={15} /> Mi finca</button>
		</div>
		{#if loading}<small>Cargando mapa…</small>{/if}
		{#if error}<small class="tag-bad">{error}</small>{/if}
	</div>
	<p class="hint">Toca un cantón para ver su detalle · toca fuera para consultar el clima del punto (NASA POWER)</p>
</div>

<style>
	.wrap { position: absolute; inset: 0; }
	.map { position: absolute; inset: 0; }
	.wrap :global(.maplibregl-ctrl-top-right) { transition: right 0.25s; }
	.wrap.panel :global(.maplibregl-ctrl-top-right) { right: 470px; }
	.wrap.panel .controls { right: 490px; }
	.controls {
		position: absolute; right: 20px; bottom: 34px; z-index: 2; transition: right 0.25s;
		display: flex; flex-direction: column; gap: 0.65rem; align-items: flex-start;
		box-shadow: var(--shadow); max-width: 260px; padding: 0.9rem; border-top: 4px solid var(--accent);
	}
	.p3d { align-self: stretch; justify-content: center; }
	.layers { position: absolute; left: 20px; bottom: 34px; z-index: 5; display: flex; flex-direction: column; align-items: flex-start; gap: 0.5rem; }
	.lbtn { width: 78px; height: 78px; border-radius: 14px; border: 2px solid #fff; background-size: cover; background-position: center; background-color: #1c231e; box-shadow: var(--shadow); cursor: pointer; position: relative; overflow: hidden; padding: 0; }
	.lbtn span { position: absolute; inset: auto 0 0 0; display: flex; justify-content: center; align-items: center; gap: 0.25rem; padding: 0.25rem 0; background: rgb(0 0 0 / 0.55); color: #fff; font-size: 0.75rem; font-weight: 700; }
	.lp { width: 330px; max-width: calc(100vw - 40px); max-height: calc(100vh - 260px); overflow: auto; display: flex; flex-direction: column; gap: 0.55rem; box-shadow: var(--shadow); }
	.ttl { font-family: var(--display); font-size: 0.98rem; color: var(--heading); }
	.x { width: 28px; height: 28px; border-radius: 999px; border: 0; background: var(--surface-2); color: var(--ink-2); display: grid; place-items: center; cursor: pointer; }
	.bases { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.3rem; }
	.dets { grid-template-columns: repeat(4, 1fr); }
	.bases button { display: flex; flex-direction: column; align-items: center; gap: 0.25rem; border: 0; background: none; padding: 0.25rem; border-radius: 10px; font-size: 0.72rem; font-weight: 600; color: var(--ink-2); cursor: pointer; text-align: center; }
	.bases button:hover { background: var(--surface-2); }
	.bases button.on { color: var(--accent); }
	.th { width: 52px; height: 52px; border-radius: 10px; background-size: cover; background-position: center; background-color: #1c231e; outline: 1px solid var(--line); outline-offset: 2px; display: grid; place-items: center; }
	.th.ic { background: var(--surface-2); color: var(--ink-2); width: 46px; height: 46px; }
	.bases button.on .th { outline: 2px solid var(--accent); }
	.bases button.on .th.ic { background: var(--accent-soft); color: var(--accent); }
	.meas { position: absolute; bottom: 34px; left: 50%; transform: translateX(-50%); z-index: 4; display: flex; gap: 0.6rem; align-items: center; box-shadow: var(--shadow); padding: 0.55rem 1rem; border-radius: 999px; white-space: nowrap; }
	.lnk { border: 0; background: none; color: var(--accent); font-weight: 700; cursor: pointer; }
	.draw { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); z-index: 5; display: flex; flex-direction: column; gap: 0.4rem; box-shadow: var(--shadow); border-top: 4px solid var(--olive); max-width: calc(100% - 24px); }
	.draw b { display: flex; align-items: center; gap: 0.4rem; font-family: var(--display); }
	.legend { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.82rem; }
	.legend i.hatch { background-image: repeating-linear-gradient(45deg, rgb(255 255 255 / 0.55) 0 2px, transparent 2px 5px) !important; }
	.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 0.45rem; vertical-align: -1px; }
	.legend small { margin-left: 0.2rem; }
	.chk { display: flex; gap: 0.4rem; align-items: center; font-size: 0.82rem; cursor: pointer; }
	.hint { position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%); margin: 0; font-size: 0.75rem; color: var(--ink-2); background: color-mix(in srgb, var(--surface) 85%, transparent); padding: 0.2rem 0.7rem; border-radius: 999px; white-space: nowrap; pointer-events: none; }
	@media (max-width: 900px) {
		.controls { left: auto; right: 12px; bottom: auto; top: 12px; max-width: 210px; padding: 0.7rem; }
		.draw { top: auto; bottom: 12px; }
		.layers { left: 12px; bottom: auto; top: 12px; }
		.lbtn { width: 60px; height: 60px; }
		.meas { bottom: auto; top: 12px; }
		.hint { display: none; }
		.wrap.panel :global(.maplibregl-ctrl-top-right) { right: 0; }
		.wrap.panel .controls { right: 12px; }
		.wrap :global(.maplibregl-ctrl-top-right) { top: auto; bottom: 46vh; }
	}
</style>
