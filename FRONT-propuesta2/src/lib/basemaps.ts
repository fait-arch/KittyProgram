// Fuentes de mapa base y capas NASA (las mismas que FRONT/src/lib/map/basemaps.ts). Gratis y sin clave.
import type { OverlayId } from '#lib/state.svelte';

const day = (back = 1) => new Date(Date.now() - back * 24 * 3600 * 1000).toISOString().slice(0, 10);
const gibs = (layer: string, time: string, level: number, ext: string) =>
	`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${time}/GoogleMapsCompatible_Level${level}/{z}/{y}/{x}.${ext}`;
const GIBS_ATTR = 'Imágenes: <a href="https://www.earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA GIBS</a>';

export type BaseId = 'satelite' | 'predeterminado' | 'hidrografico' | 'nasa' | 'bluemarble';

/** Tipos de mapa del modo 3D (como «Tipo de mapa» de Google Maps) */
export const BASES: Record<BaseId, { label: string; detail: string; thumb: string }> = {
	satelite: { label: 'Satélite', detail: 'Sentinel-2 sin nubes 2024 · ~10 m (Copernicus / EOX)', thumb: 'url(https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/6/32/17.jpg)' },
	predeterminado: { label: 'Predeterminado', detail: 'Calles, ríos, pueblos y nombres · OpenStreetMap (OpenFreeMap)', thumb: 'linear-gradient(135deg,#f2efe9 0 45%,#cfe6c3 45% 60%,#aad3df 60%)' },
	hidrografico: { label: 'Hidrográfico', detail: 'Relieve sombreado y ríos por tipo · AWS Terrain + OpenStreetMap', thumb: 'linear-gradient(155deg,#26292b 0 38%,#3ff0ff 38% 42%,#1d2022 42% 66%,#5fe08a 66% 69%,#2b2f31 69% 88%,#f2d64b 88% 90%,#1d2022 90%)' },
	nasa: { label: 'NASA hoy', detail: 'VIIRS color real de ayer · ~250 m (NASA Worldview / GIBS)', thumb: `url(${gibs('VIIRS_SNPP_CorrectedReflectance_TrueColor', day(2), 9, 'jpg').replace('{z}/{y}/{x}', '3/4/2')})` },
	bluemarble: { label: 'Blue Marble', detail: 'La Tierra con relieve y fondo marino · NASA (GIBS)', thumb: `url(${gibs('BlueMarble_ShadedRelief_Bathymetry', 'default', 8, 'jpeg').replace('{z}/{y}/{x}', '2/2/1')})` }
};

const DEM = {
	type: 'raster-dem', tileSize: 256, maxzoom: 13, encoding: 'terrarium',
	tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
	attribution: '<a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">Terrain Tiles</a> (AWS)'
};
const LABELS = {
	type: 'raster', tileSize: 256, maxzoom: 14,
	tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/overlay_bright_3857/default/g/{z}/{y}/{x}.png'],
	attribution: 'Nombres © OpenStreetMap, EOX'
};
const OFM = { type: 'vector', url: 'https://tiles.openfreemap.org/planet', attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © OpenStreetMap' };

/** Estilo del modo 3D para cada tipo de mapa. Siempre trae el relieve 'dem'; los ráster traen 'labels' encima. */
export function style3d(base: BaseId): any {
	if (base === 'predeterminado') return 'https://tiles.openfreemap.org/styles/liberty'; // 'dem' se agrega al cargar
	if (base === 'hidrografico') {
		const color: any = ['match', ['get', 'class'], 'river', '#3ff0ff', 'stream', '#5fe08a', 'canal', '#f2d64b', 'drain', '#f2d64b', '#2fc6c9'];
		const width: any = ['interpolate', ['exponential', 1.6], ['zoom'], 5, ['match', ['get', 'class'], 'river', 1.1, 0.4], 10, ['match', ['get', 'class'], 'river', 2.6, 1.1], 14, ['match', ['get', 'class'], 'river', 5, 2.2]];
		return {
			version: 8, sources: { ofm: OFM, dem: DEM, labels: LABELS },
			layers: [
				{ id: 'fondo', type: 'background', paint: { 'background-color': '#1f2c25' } },
				{ id: 'relieve', type: 'hillshade', source: 'dem', paint: { 'hillshade-exaggeration': 0.85, 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#b9c2b4', 'hillshade-accent-color': '#2a332d' } },
				{ id: 'agua', type: 'fill', source: 'ofm', 'source-layer': 'water', paint: { 'fill-color': '#3f8a80', 'fill-opacity': 0.85 } },
				{ id: 'rio-brillo', type: 'line', source: 'ofm', 'source-layer': 'waterway', layout: { 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': ['*', 3.2, width], 'line-blur': 3, 'line-opacity': 0.35 } },
				{ id: 'rio', type: 'line', source: 'ofm', 'source-layer': 'waterway', layout: { 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': width, 'line-opacity': 0.95 } },
				{ id: 'labels', type: 'raster', source: 'labels' }
			]
		};
	}
	const tiles: Record<string, { tiles: string[]; maxzoom: number; attribution: string }> = {
		satelite: { tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg'], maxzoom: 14, attribution: '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless</a> by EOX (Copernicus Sentinel 2024)' },
		nasa: { tiles: [gibs('VIIRS_SNPP_CorrectedReflectance_TrueColor', day(1), 9, 'jpg')], maxzoom: 9, attribution: `${GIBS_ATTR} · VIIRS SNPP` },
		bluemarble: { tiles: [gibs('BlueMarble_ShadedRelief_Bathymetry', 'default', 8, 'jpeg')], maxzoom: 8, attribution: `${GIBS_ATTR} · Blue Marble` }
	};
	const t = tiles[base];
	return {
		version: 8,
		sources: { sat: { type: 'raster', tileSize: 256, ...t }, labels: LABELS, dem: DEM },
		layers: [
			{ id: 'fondo', type: 'background', paint: { 'background-color': '#18231d' } },
			{ id: 'sat', type: 'raster', source: 'sat', paint: { 'raster-saturation': -0.1, 'raster-brightness-max': 0.95 } },
			{ id: 'relieve', type: 'hillshade', source: 'dem', paint: { 'hillshade-exaggeration': 0.3, 'hillshade-shadow-color': '#000000' } },
			{ id: 'labels', type: 'raster', source: 'labels' }
		]
	};
}
export const DEM_SOURCE = DEM;

/** Ícono de mazorca dibujado en canvas (sin archivos): uno por color de zona */
export function cacaoIcon(fill: string, size = 48): ImageData {
	const c = document.createElement('canvas');
	c.width = c.height = size;
	const g = c.getContext('2d')!;
	g.scale(size / 48, size / 48); g.translate(24, 24); g.rotate(-0.45);
	g.shadowColor = 'rgba(0,0,0,.45)'; g.shadowBlur = 4; g.shadowOffsetY = 1.5;
	g.beginPath(); g.moveTo(0, -20); g.bezierCurveTo(11, -15, 13, 12, 0, 20); g.bezierCurveTo(-13, 12, -11, -15, 0, -20); g.closePath();
	g.fillStyle = fill; g.fill();
	g.shadowColor = 'transparent'; g.lineWidth = 2.5; g.strokeStyle = '#ffffff'; g.stroke();
	g.lineWidth = 1.4; g.strokeStyle = 'rgba(0,0,0,.28)';
	for (const k of [-5, 0, 5]) { g.beginPath(); g.moveTo(k * 0.6, -17); g.quadraticCurveTo(k * 1.25, 0, k * 0.6, 17); g.stroke(); }
	g.beginPath(); g.moveTo(0, -20); g.lineTo(0, -24); g.lineWidth = 2.5; g.strokeStyle = '#4b3a2f'; g.stroke();
	return g.getImageData(0, 0, size, size);
}

export const haversineKm = (a: [number, number], b: [number, number]) => {
	const r = (d: number) => (d * Math.PI) / 180;
	const h = Math.sin(r(b[1] - a[1]) / 2) ** 2 + Math.cos(r(a[1])) * Math.cos(r(b[1])) * Math.sin(r(b[0] - a[0]) / 2) ** 2;
	return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
};

export const OVERLAYS: Record<OverlayId, { label: string; layers: string[]; times: () => string[]; ext: string; levels: number[]; opacity: number; stackDays?: number }> = {
	lluvia: { label: 'Lluvia', layers: ['IMERG_Precipitation_Rate'], times: () => [`${day(1)}T12:00:00Z`, `${day(2)}T12:00:00Z`, day(1)], ext: 'png', levels: [6, 7, 5, 8], opacity: 0.75 },
	vegetacion: { label: 'Vegetación', layers: ['MODIS_Terra_NDVI_8Day'], times: () => ['default', day(8)], ext: 'png', levels: [9, 8, 7], opacity: 0.7 },
	incendios: {
		label: 'Incendios', layers: ['VIIRS_SNPP_Thermal_Anomalies_375m_All', 'VIIRS_NOAA20_Thermal_Anomalies_375m_All', 'MODIS_Terra_Thermal_Anomalies_All'],
		times: () => [day(1), day(2), day(3)], ext: 'png', levels: [9, 8, 7, 10], opacity: 1, stackDays: 7
	},
	temperatura: { label: 'Temperatura', layers: ['MODIS_Terra_Land_Surface_Temp_Day'], times: () => [day(2), day(3), 'default'], ext: 'png', levels: [7, 6, 8], opacity: 0.65 },
	aire: { label: 'Calidad del aire', layers: ['MODIS_Combined_Value_Added_AOD', 'MODIS_Terra_Aerosol_Optical_Depth_3km', 'MODIS_Terra_Aerosol'], times: () => [day(1), day(2)], ext: 'png', levels: [6, 7, 5], opacity: 0.6 }
};

export type OverlaySource = { urls: string[]; maxzoom: number; attribution: string; opacity: number };

/** Busca la combinación capa / fecha / nivel que GIBS sirve (pide una tesela de zoom 0). Se recuerda en la sesión. */
export async function resolveOverlay(id: OverlayId): Promise<OverlaySource | null> {
	const key = `cr-gibs2-${id}-${day(1)}`;
	try { const hit = sessionStorage.getItem(key); if (hit) return JSON.parse(hit); } catch { /* */ }
	const o = OVERLAYS[id];
	for (const layer of o.layers)
		for (const time of o.times())
			for (const level of o.levels) {
				const url = gibs(layer, time, level, o.ext);
				try {
					const r = await fetch(url.replace('{z}/{y}/{x}', '0/0/0'), { cache: 'force-cache' });
					if (r.ok && (r.headers.get('content-type') ?? '').startsWith('image')) {
						const urls = o.stackDays ? Array.from({ length: o.stackDays }, (_, i) => gibs(layer, day(i + 1), level, o.ext)) : [url];
						const out = { urls, maxzoom: level, attribution: `${GIBS_ATTR} · ${o.label}`, opacity: o.opacity };
						try { sessionStorage.setItem(key, JSON.stringify(out)); } catch { /* */ }
						return out;
					}
				} catch { /* probar la siguiente */ }
			}
	return null;
}
