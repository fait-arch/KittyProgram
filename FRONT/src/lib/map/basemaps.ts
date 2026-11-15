/**
 * Fuentes del mapa satelital, todas gratis y sin clave, cargadas directo desde el navegador.
 * Revisadas: Copernicus Data Space / EOX, NASA Worldview (GIBS), USGS EarthExplorer, OpenFreeMap (OpenStreetMap).
 */
export type BasemapId = "predeterminado" | "satelite" | "hidrografico" | "nasa" | "bluemarble";

const day = (back = 1) => new Date(Date.now() - back * 24 * 3600 * 1000).toISOString().slice(0, 10);
const gibs = (layer: string, time: string, level: number, ext: string) =>
  `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${time}/GoogleMapsCompatible_Level${level}/{z}/{y}/{x}.${ext}`;
const GIBS_ATTR = 'Imágenes: <a href="https://www.earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA GIBS</a> (ESDIS)';

/** Tipo de mapa (como «Predeterminado / Satélite» de Google Maps) */
export const BASEMAPS: Record<BasemapId, { label: string; detail: string; thumb: string; style?: string; tiles?: string[]; maxzoom?: number; attribution?: string; hydro?: boolean }> = {
  predeterminado: {
    label: "Predeterminado",
    detail: "Calles, ríos, pueblos y nombres · OpenStreetMap (OpenFreeMap)",
    thumb: "linear-gradient(135deg,#f2efe9 0 45%,#cfe6c3 45% 60%,#aad3df 60%)",
    style: "https://tiles.openfreemap.org/styles/liberty",
  },
  satelite: {
    label: "Satélite",
    detail: "Sentinel-2 sin nubes 2024 · ~10 m (Copernicus / EOX)",
    thumb: "url(https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/6/32/17.jpg)",
    tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg"],
    maxzoom: 14,
    // Licencia CC BY-NC-SA 4.0: uso no comercial con atribución
    attribution: '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless - https://s2maps.eu</a> by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2024)',
  },
  hidrografico: {
    label: "Hidrográfico",
    detail: "Relieve sombreado y ríos · AWS Terrain Tiles + OpenStreetMap (OpenFreeMap)",
    thumb: "linear-gradient(155deg,#26292b 0 38%,#3ff0ff 38% 42%,#1d2022 42% 66%,#5fe08a 66% 69%,#2b2f31 69% 88%,#f2d64b 88% 90%,#1d2022 90%)",
    hydro: true,
  },
  nasa: {
    label: "NASA hoy",
    detail: "VIIRS color real de ayer · ~250 m (NASA Worldview / GIBS)",
    thumb: `url(${gibs("VIIRS_SNPP_CorrectedReflectance_TrueColor", day(2), 9, "jpg").replace("{z}/{y}/{x}", "3/4/2")})`,
    tiles: [gibs("VIIRS_SNPP_CorrectedReflectance_TrueColor", day(1), 9, "jpg")],
    maxzoom: 9,
    attribution: `${GIBS_ATTR} · VIIRS SNPP`,
  },
  bluemarble: {
    label: "Blue Marble",
    detail: "La Tierra con relieve y fondo marino · NASA (GIBS)",
    thumb: `url(${gibs("BlueMarble_ShadedRelief_Bathymetry", "default", 8, "jpeg").replace("{z}/{y}/{x}", "2/2/1")})`,
    tiles: [gibs("BlueMarble_ShadedRelief_Bathymetry", "default", 8, "jpeg")],
    maxzoom: 8,
    attribution: `${GIBS_ATTR} · Blue Marble`,
  },
};

/** Nombres de lugares sobre el satélite (como «Etiquetas» de Google Maps) */
export const LABELS_OVERLAY = {
  tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/overlay_bright_3857/default/g/{z}/{y}/{x}.png"],
  attribution: "Nombres: Data © OpenStreetMap contributors, Rendering © EOX",
};

/** Elevación global (Terrarium) en AWS Open Data: relieve 3D sin clave */
export const TERRAIN = {
  tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  encoding: "terrarium" as const,
  maxzoom: 13,
  attribution: '<a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">Terrain Tiles</a> (AWS Open Data)',
};

/** Capas de datos NASA (como «Detalles del mapa»). El nivel de zoom se detecta al activarlas. */
export type OverlayId = "lluvia" | "vegetacion" | "incendios" | "temperatura" | "aire";
export const OVERLAYS: Record<OverlayId, { label: string; icon: string; detail: string; layers: string[]; times: () => string[]; ext: string; levels: number[]; opacity: number; stackDays?: number }> = {
  lluvia: { label: "Lluvia", icon: "rainy", detail: "Lluvia de ayer · NASA GPM IMERG", layers: ["IMERG_Precipitation_Rate"],
    times: () => [`${day(1)}T12:00:00Z`, `${day(2)}T12:00:00Z`, day(1)], ext: "png", levels: [6, 7, 5, 8], opacity: 0.75 },
  vegetacion: { label: "Vegetación", icon: "forest", detail: "Verdor de la vegetación (NDVI) de 8 días · MODIS", layers: ["MODIS_Terra_NDVI_8Day"],
    times: () => ["default", day(8)], ext: "png", levels: [9, 8, 7], opacity: 0.7 },
  // Los focos son puntos pequeños y no hay incendios todos los días: se suman los últimos 7 días
  incendios: { label: "Incendios", icon: "local_fire_department", detail: "Focos de calor de los últimos 7 días · VIIRS (FIRMS). Son puntos pequeños: acérquese para verlos",
    layers: ["VIIRS_SNPP_Thermal_Anomalies_375m_All", "VIIRS_NOAA20_Thermal_Anomalies_375m_All", "MODIS_Terra_Thermal_Anomalies_All"],
    times: () => [day(1), day(2), day(3)], ext: "png", levels: [9, 8, 7, 10], opacity: 1, stackDays: 7 },
  temperatura: { label: "Temperatura", icon: "device_thermostat", detail: "Temperatura de la superficie de día · MODIS", layers: ["MODIS_Terra_Land_Surface_Temp_Day"],
    times: () => [day(2), day(3), "default"], ext: "png", levels: [7, 6, 8], opacity: 0.65 },
  aire: { label: "Calidad del aire", icon: "air", detail: "Aerosoles en el aire (humo, polvo) · MODIS", layers: ["MODIS_Combined_Value_Added_AOD", "MODIS_Terra_Aerosol_Optical_Depth_3km", "MODIS_Terra_Aerosol"],
    times: () => [day(1), day(2)], ext: "png", levels: [6, 7, 5], opacity: 0.6 },
};

export type OverlaySource = { urls: string[]; maxzoom: number; attribution: string };

/**
 * Busca la combinación capa / fecha / nivel que GIBS sirve, pidiendo una sola tesela (zoom 0).
 * Devuelve una URL por capa a dibujar (varias si la capa suma días). Se recuerda en la sesión.
 */
export async function resolveOverlay(id: OverlayId): Promise<OverlaySource | null> {
  const key = `cr-gibs2-${id}-${day(1)}`;
  try {
    const hit = sessionStorage.getItem(key);
    if (hit) return JSON.parse(hit);
  } catch { /* sin almacenamiento */ }
  const o = OVERLAYS[id];
  for (const layer of o.layers)
    for (const time of o.times())
      for (const level of o.levels) {
        const url = gibs(layer, time, level, o.ext);
        try {
          const r = await fetch(url.replace("{z}/{y}/{x}", "0/0/0"), { method: "GET", cache: "force-cache" });
          if (r.ok && (r.headers.get("content-type") ?? "").startsWith("image")) {
            const urls = o.stackDays ? Array.from({ length: o.stackDays }, (_, i) => gibs(layer, day(i + 1), level, o.ext)) : [url];
            const out: OverlaySource = { urls, maxzoom: level, attribution: `${GIBS_ATTR} · ${o.label}` };
            try { sessionStorage.setItem(key, JSON.stringify(out)); } catch { /* */ }
            return out;
          }
        } catch { /* sin red: probar la siguiente */ }
      }
  return null; // no se recuerda el fallo: se reintenta la próxima vez

}

/** Ríos y cuerpos de agua (OpenMapTiles de OpenFreeMap, sin clave) para el mapa hidrográfico */
export const HYDRO = {
  tilejson: "https://tiles.openfreemap.org/planet",
  attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  /** Color por tipo de curso de agua, como en los mapas de caudal: ríos cian, quebradas verdes, canales amarillos */
  colors: { river: "#3ff0ff", stream: "#5fe08a", canal: "#f2d64b", other: "#2fc6c9" },
};
