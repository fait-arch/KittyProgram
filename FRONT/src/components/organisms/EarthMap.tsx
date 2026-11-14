"use client";
/**
 * Organismo · mapa satelital 3D tipo Google Maps (MapLibre GL JS 5, BSD-3).
 * Botón «Capas» abajo a la izquierda: Tipo de mapa (Predeterminado, Satélite, NASA hoy, Blue Marble; Globo y
 * Etiquetas), Detalles del mapa (relieve, columnas 3D, cacao apto y capas NASA: lluvia, vegetación, incendios,
 * temperatura, calidad del aire) y Herramientas (medir, mi ubicación, pantalla completa).
 * Misma escala de alerta de 5 niveles que el mapa 2D y QGIS.
 */
import "maplibre-gl/dist/maplibre-gl.css";
import maplibregl, { type GeoJSONSource, type Map as MLMap, type StyleSpecification } from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Feature, FeatureCollection, LineString, Point, Polygon, MultiPolygon } from "geojson";
import type { AreasGeoJSON, Zone, ZoneItem } from "@/lib/api/types";
import { LOSS_RAMP, lossClassIndex, RISK_LABEL, riskClassOf, ZONE_COLORS, ZONE_META, type Theme } from "@/lib/design/colors";
import { BASEMAPS, LABELS_OVERLAY, OVERLAYS, resolveOverlay, TERRAIN, type BasemapId, type OverlayId, type OverlaySource } from "@/lib/map/basemaps";
import { cacaoIcon, hatchPattern } from "@/lib/map/cacaoIcon";
import { pointInGeometry, ringAreaHa, ringCentroid, type LonLat } from "@/lib/geo/finca";
import { fmt1, fmtInt, fmtPct } from "@/lib/design/format";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

export type EarthMode = "perdida" | "zonas";
const ZONE_HEX = ZONE_COLORS.mision;
const APT_MIN = 0.7; // aptitud ECOCROP alta = zona apta para sembrar
const OWN = new Set(["cr-dem", "cr-cantones", "cr-cacao", "cr-medida", "cr-etiquetas"]);

function labelPoint(g: Polygon | MultiPolygon): LonLat {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  const ring = polys.map((p) => p[0]).sort((a, b) => b.length - a.length)[0] as LonLat[];
  const c = ringCentroid(ring);
  if (pointInGeometry(c, g)) return c;
  const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}
const haversineKm = (a: LonLat, b: LonLat) => {
  const r = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(r(b[1] - a[1]) / 2) ** 2 + Math.cos(r(a[1])) * Math.cos(r(b[1])) * Math.sin(r(b[0] - a[0]) / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
};

type Opts = { base: BasemapId; globe: boolean; labels: boolean; terrain: boolean; columns: boolean; cacao: boolean; overlays: OverlayId[] };

export default function EarthMap({ areas, values, zones, mode, selectedId, onSelect, theme, ariaLabel }: {
  areas?: AreasGeoJSON;
  values: Map<string, number>;
  zones?: ZoneItem[];
  mode: EarthMode;
  selectedId?: string | null;
  onSelect: (id: string) => void;
  theme: Theme;
  ariaLabel: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(0); // aumenta en cada carga de estilo
  const [opts, setOpts] = useState<Opts>({ base: "satelite", globe: true, labels: true, terrain: true, columns: false, cacao: true, overlays: [] });
  const [panel, setPanel] = useState(false);
  const [overlayState, setOverlayState] = useState<Partial<Record<OverlayId, "cargando" | "ok" | "no">>>({});
  const overlaySrc = useRef<Partial<Record<OverlayId, OverlaySource>>>({});
  const [measuring, setMeasuring] = useState(false);
  const [measure, setMeasure] = useState<LonLat[]>([]);
  const [baseError, setBaseError] = useState<string | null>(null);
  const latest = useRef({ onSelect, measuring, measure, opts, mode, selectedId });
  latest.current = { onSelect, measuring, measure, opts, mode, selectedId };

  // Datos: cantones con color/altura y mazorcas en cantones aptos
  const zoneById = useMemo(() => new Map((zones ?? []).map((z) => [z.area_id, z])), [zones]);
  const data = useMemo(() => {
    if (!areas) return null;
    const cantons: FeatureCollection = { type: "FeatureCollection", features: areas.features.map((f) => {
      const v = values.get(f.properties.id);
      const z = zoneById.get(f.properties.id);
      return { ...f, id: undefined, properties: {
        id: f.properties.id, name: f.properties.name, province: f.properties.province,
        loss: v ?? null, level: v != null ? lossClassIndex(v) : -1, color: v != null ? LOSS_RAMP[lossClassIndex(v)] : "#5e6b60",
        zone: z?.zone ?? null, zcolor: z ? ZONE_HEX[z.zone] : "#5e6b60", height: v != null ? Math.max(800, v * 1600) : 0,
      } } as Feature;
    }) };
    const pts: FeatureCollection<Point> = { type: "FeatureCollection", features: [] };
    for (const f of areas.features) {
      const z = zoneById.get(f.properties.id);
      if (!z || z.suitability_score < APT_MIN) continue;
      pts.features.push({ type: "Feature", geometry: { type: "Point", coordinates: labelPoint(f.geometry as Polygon | MultiPolygon) },
        properties: { id: f.properties.id, name: f.properties.name, zone: z.zone, icon: `cacao-${z.zone}` } });
    }
    return { cantons, pts };
  }, [areas, values, zoneById]);
  const dataRef = useRef(data);
  dataRef.current = data;

  /** Capas NASA: una fuente/capa raster por URL (incendios suma 7 días) */
  const overlayParts = (id: OverlayId) => {
    const s = overlaySrc.current[id];
    if (!s) return [];
    return s.urls.map((url, i) => ({
      id: `cr-ov-${id}-${i}`,
      source: { type: "raster" as const, tiles: [url], tileSize: 256, maxzoom: s.maxzoom, attribution: i === 0 ? s.attribution : undefined },
      layer: { id: `cr-ov-${id}-${i}`, type: "raster" as const, source: `cr-ov-${id}-${i}`,
        paint: { "raster-opacity": OVERLAYS[id].opacity, "raster-fade-duration": 0, ...(OVERLAYS[id].stackDays ? { "raster-resampling": "nearest" as const } : {}) } },
    }));
  };

  /** Fuentes y capas propias, que se agregan sobre cualquier tipo de mapa */
  const addOwn = useCallback((style: StyleSpecification): StyleSpecification => {
    const d = dataRef.current;
    const empty: FeatureCollection = { type: "FeatureCollection", features: [] };
    const o = latest.current.opts;
    const sources: StyleSpecification["sources"] = {
      ...style.sources,
      "cr-dem": { type: "raster-dem", tiles: TERRAIN.tiles, encoding: TERRAIN.encoding, tileSize: 256, maxzoom: TERRAIN.maxzoom, attribution: TERRAIN.attribution },
      "cr-cantones": { type: "geojson", data: d?.cantons ?? empty },
      "cr-cacao": { type: "geojson", data: d?.pts ?? empty },
      "cr-medida": { type: "geojson", data: empty },
      "cr-etiquetas": { type: "raster", tiles: LABELS_OVERLAY.tiles, tileSize: 256, maxzoom: 14, attribution: LABELS_OVERLAY.attribution },
    };
    const overlayLayers: StyleSpecification["layers"] = [];
    for (const id of o.overlays)
      for (const part of overlayParts(id)) { sources[part.id] = part.source; overlayLayers.push(part.layer); }
    const vis = (b: boolean) => (b ? "visible" : "none") as "visible" | "none";
    const isRaster = o.base !== "predeterminado";
    return {
      ...style,
      projection: { type: o.globe ? "globe" : "mercator" },
      sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
      ...(o.terrain ? { terrain: { source: "cr-dem", exaggeration: 1.6 } } : {}),
      sources,
      layers: [
        ...style.layers.map((l) => (!isRaster && l.type === "symbol" ? { ...l, layout: { ...l.layout, visibility: vis(o.labels) } } : l)),
        ...overlayLayers,
        { id: "cr-relieve", type: "hillshade", source: "cr-dem", layout: { visibility: vis(o.terrain && isRaster) }, paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#000000" } },
        { id: "cr-cantones-relleno", type: "fill", source: "cr-cantones", layout: { visibility: vis(!o.columns) }, paint: { "fill-color": ["get", "color"], "fill-opacity": isRaster ? 0.55 : 0.6 } },
        { id: "cr-cantones-critica", type: "fill", source: "cr-cantones", filter: ["==", ["get", "level"], 4], paint: { "fill-pattern": "rayado", "fill-opacity": 0.8 } },
        { id: "cr-cantones-3d", type: "fill-extrusion", source: "cr-cantones", layout: { visibility: vis(o.columns) },
          paint: { "fill-extrusion-color": ["get", "color"], "fill-extrusion-height": ["get", "height"], "fill-extrusion-opacity": 0.88 } },
        { id: "cr-cantones-borde", type: "line", source: "cr-cantones", paint: { "line-color": isRaster ? "#ffffff" : "#14261c", "line-opacity": 0.55, "line-width": 0.6 } },
        { id: "cr-cantones-sel", type: "line", source: "cr-cantones", filter: ["==", ["get", "id"], ""], paint: { "line-color": isRaster ? "#ffffff" : "#14261c", "line-width": 3.5 } },
        { id: "cr-etiquetas", type: "raster", source: "cr-etiquetas", layout: { visibility: vis(o.labels && isRaster) } },
        { id: "cr-cacao", type: "symbol", source: "cr-cacao", layout: { visibility: vis(o.cacao), "icon-image": ["get", "icon"],
          "icon-size": ["interpolate", ["linear"], ["zoom"], 5, 0.45, 9, 0.9], "icon-allow-overlap": true } },
        { id: "cr-medida-linea", type: "line", source: "cr-medida", paint: { "line-color": "#ffffff", "line-width": 3, "line-dasharray": [2, 1.5] } },
        { id: "cr-medida-puntos", type: "circle", source: "cr-medida", filter: ["==", ["geometry-type"], "Point"],
          paint: { "circle-radius": 5, "circle-color": "#5bdb87", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } },
      ],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Estilo raster (satélite, NASA, Blue Marble) ya con las capas propias */
  const rasterStyle = useCallback((id: BasemapId): StyleSpecification => {
    const b = BASEMAPS[id];
    return addOwn({
      version: 8,
      sources: { base: { type: "raster", tiles: b.tiles!, tileSize: 256, maxzoom: b.maxzoom, attribution: b.attribution } },
      layers: [{ id: "fondo", type: "background", paint: { "background-color": "#07120d" } }, { id: "base", type: "raster", source: "base" }],
    });
  }, [addOwn]);

  /** Solo el cambio de «Tipo de mapa» reconstruye el estilo; lo demás se cambia sobre el mapa cargado */
  const styleOk = useRef(false);
  const applyBase = useCallback(() => {
    const m = map.current;
    if (!m) return;
    const b = BASEMAPS[latest.current.opts.base];
    styleOk.current = false;
    if (b.style) m.setStyle(b.style, { transformStyle: (_prev, next) => addOwn(next as StyleSpecification) });
    else m.setStyle(rasterStyle(latest.current.opts.base));
  }, [addOwn, rasterStyle]);

  // 1. Crear el mapa. Se difiere un instante: en desarrollo React monta dos veces y el primer
  //    montaje se cancela antes de crear nada (así no queda un mapa a medio cargar que falle).
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    let m: MLMap | null = null;
    const timer = window.setTimeout(() => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const base = latest.current.opts.base;
      m = new maplibregl.Map({
        container: node,
        style: BASEMAPS[base].style ? rasterStyle("satelite") : rasterStyle(base),
        center: [-79.6, -1.3],
        zoom: reduce ? 6.4 : 1.8,
        pitch: reduce ? 40 : 0,
        maxPitch: 80,
        attributionControl: { compact: true },
      });
      const mm = m;
      map.current = mm;
      mm.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      mm.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: false }), "top-right");
      mm.addControl(new maplibregl.FullscreenControl({ container: wrap.current ?? undefined }), "top-right");
      mm.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
      // Íconos propios: se vuelven a pedir en cada cambio de estilo
      mm.on("styleimagemissing", (e) => {
        if (mm.hasImage(e.id)) return;
        if (e.id === "rayado") mm.addImage("rayado", hatchPattern());
        else if (e.id.startsWith("cacao-")) mm.addImage(e.id, cacaoIcon(ZONE_HEX[e.id.slice(6) as Zone] ?? "#5bdb87"), { pixelRatio: 2 });
      });
      mm.on("style.load", () => { styleOk.current = true; setReady((n) => n + 1); });
      mm.on("error", (e) => {
        const src = (e as unknown as { sourceId?: string }).sourceId;
        if (src === "base") setBaseError(latest.current.opts.base);
      });
      if (node.clientWidth > 900) mm.setPadding({ left: 300, top: 110, right: 40, bottom: 20 });
      mm.once("style.load", () => {
        if (BASEMAPS[latest.current.opts.base].style) applyBase();
        if (!reduce) mm.flyTo({ center: [-79.75, -1.35], zoom: 6.5, pitch: 48, bearing: -14, duration: 5200, essential: false });
      });
      // Cantones: tooltip y selección
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: "cr-popup", offset: 12 });
      const hover = (e: maplibregl.MapLayerMouseEvent) => {
        if (latest.current.measuring) return;
        const f = e.features?.[0];
        if (!f) return;
        mm.getCanvas().style.cursor = "pointer";
        const p = f.properties as { name: string; province: string; loss: number | string | null; zone: Zone | null };
        const loss = p.loss == null || p.loss === "null" ? null : Number(p.loss);
        pop.setLngLat(e.lngLat).setHTML(`<b>${p.name}</b> · ${p.province}<br>${loss != null ? `${fmtPct(loss)} · pérdida ${RISK_LABEL[riskClassOf(loss)].toLowerCase()}` : "sin datos"}${p.zone ? `<br>Zona 2050: ${ZONE_META[p.zone].label}` : ""}`).addTo(mm);
      };
      for (const l of ["cr-cantones-relleno", "cr-cantones-3d"]) {
        mm.on("mousemove", l, hover);
        mm.on("mouseleave", l, () => { mm.getCanvas().style.cursor = latest.current.measuring ? "crosshair" : ""; pop.remove(); });
      }
      mm.on("click", (e) => {
        if (latest.current.measuring) { setMeasure((p) => [...p, [e.lngLat.lng, e.lngLat.lat]]); return; }
        const f = mm.queryRenderedFeatures(e.point, { layers: ["cr-cacao", "cr-cantones-3d", "cr-cantones-relleno"].filter((l) => mm.getLayer(l)) })[0];
        const id = f?.properties?.id;
        if (id) latest.current.onSelect(String(id));
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      styleOk.current = false;
      if (m) { try { m.remove(); } catch { /* ya liberado */ } }
      map.current = null;
    };
  }, [rasterStyle, applyBase]);

  // 2. Tipo de mapa → único cambio que reconstruye el estilo
  const firstBase = useRef(true);
  useEffect(() => {
    if (firstBase.current) { firstBase.current = false; return; }
    setBaseError(null);
    applyBase();
  }, [opts.base, applyBase]);

  // 3. Globo, relieve y etiquetas sobre el mapa ya cargado
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !styleOk.current) return;
    const isRaster = opts.base !== "predeterminado";
    m.setProjection({ type: opts.globe ? "globe" : "mercator" });
    m.setTerrain(opts.terrain ? { source: "cr-dem", exaggeration: 1.6 } : null);
    if (m.getLayer("cr-relieve")) m.setLayoutProperty("cr-relieve", "visibility", opts.terrain && isRaster ? "visible" : "none");
    if (m.getLayer("cr-etiquetas")) m.setLayoutProperty("cr-etiquetas", "visibility", opts.labels && isRaster ? "visible" : "none");
    if (!isRaster)
      for (const l of m.getStyle().layers)
        if (l.type === "symbol" && !l.id.startsWith("cr-")) m.setLayoutProperty(l.id, "visibility", opts.labels ? "visible" : "none");
  }, [opts.globe, opts.terrain, opts.labels, opts.base, ready]);

  // 4. Capas NASA: se agregan o quitan sin tocar el resto del mapa
  const overlayKey = opts.overlays.filter((o) => overlayState[o] === "ok").join(",");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !styleOk.current) return;
    const on = new Set(overlayKey ? overlayKey.split(",") : []);
    for (const id of Object.keys(OVERLAYS) as OverlayId[])
      for (const part of overlayParts(id)) {
        const has = !!m.getLayer(part.id);
        if (on.has(id) && !has) {
          if (!m.getSource(part.id)) m.addSource(part.id, part.source);
          m.addLayer(part.layer, m.getLayer("cr-relieve") ? "cr-relieve" : undefined);
        } else if (!on.has(id) && has) {
          m.removeLayer(part.id);
          if (m.getSource(part.id)) m.removeSource(part.id);
        }
      }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlayKey, ready]);

  // 5. Datos, modo, selección, columnas y cacao (sin reconstruir el estilo)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !styleOk.current || !data || !m.getSource("cr-cantones")) return;
    (m.getSource("cr-cantones") as GeoJSONSource).setData(data.cantons);
    (m.getSource("cr-cacao") as GeoJSONSource).setData(data.pts);
    const col = mode === "zonas" ? ["get", "zcolor"] : ["get", "color"];
    m.setPaintProperty("cr-cantones-relleno", "fill-color", col as never);
    m.setPaintProperty("cr-cantones-3d", "fill-extrusion-color", col as never);
    m.setLayoutProperty("cr-cantones-critica", "visibility", mode === "perdida" && !opts.columns ? "visible" : "none");
    m.setLayoutProperty("cr-cantones-3d", "visibility", opts.columns ? "visible" : "none");
    m.setLayoutProperty("cr-cantones-relleno", "visibility", opts.columns ? "none" : "visible");
    m.setLayoutProperty("cr-cacao", "visibility", opts.cacao ? "visible" : "none");
    m.setFilter("cr-cantones-sel", ["==", ["get", "id"], selectedId ?? ""]);
  }, [data, mode, selectedId, opts.columns, opts.cacao, ready]);

  useEffect(() => {
    const m = map.current;
    if (opts.columns && m && m.getPitch() < 40) m.easeTo({ pitch: 55, duration: 800 });
  }, [opts.columns]);

  // Acercar al cantón elegido
  useEffect(() => {
    const m = map.current;
    if (!m || !selectedId || !data) return;
    const f = data.pts.features.find((p) => p.properties?.id === selectedId);
    const c = data.cantons.features.find((x) => x.properties?.id === selectedId);
    const pt = f ? (f.geometry.coordinates as LonLat) : c ? labelPoint(c.geometry as Polygon) : null;
    if (pt) m.easeTo({ center: pt, zoom: Math.max(m.getZoom(), 8.2), duration: 1200 });
  }, [selectedId, data]);

  // 6. Medir distancia y área
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !styleOk.current || !m.getSource("cr-medida")) return;
    const feats: Feature[] = measure.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: {} }));
    if (measure.length > 1) feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: measure } as LineString, properties: {} });
    (m.getSource("cr-medida") as GeoJSONSource).setData({ type: "FeatureCollection", features: feats });
    m.getCanvas().style.cursor = measuring ? "crosshair" : "";
    if (measuring) m.doubleClickZoom.disable(); else m.doubleClickZoom.enable();
  }, [measure, measuring, ready]);
  const distKm = measure.slice(1).reduce((s, p, i) => s + haversineKm(measure[i], p), 0);
  const areaHa = measure.length >= 3 ? ringAreaHa(measure) : 0;

  // Capas NASA: al activarlas se busca la fuente que responde
  const toggleOverlay = async (id: OverlayId) => {
    const on = opts.overlays.includes(id);
    setOpts((o) => ({ ...o, overlays: on ? o.overlays.filter((x) => x !== id) : [...o.overlays, id] }));
    if (on || overlaySrc.current[id]) return;
    setOverlayState((s) => ({ ...s, [id]: "cargando" }));
    const r = await resolveOverlay(id);
    if (r) overlaySrc.current[id] = r;
    setOverlayState((s) => ({ ...s, [id]: r ? "ok" : "no" }));
    if (!r) setOpts((o) => ({ ...o, overlays: o.overlays.filter((x) => x !== id) }));
  };

  const set = <K extends keyof Opts>(k: K, v: Opts[K]) => setOpts((o) => ({ ...o, [k]: v }));
  const nApt = data?.pts.features.length ?? 0;
  const chip = (on: boolean) => cn("state-layer flex flex-col items-center gap-1 rounded-md p-1.5 text-[12px] font-semibold cursor-pointer", on ? "text-primary" : "text-on-surface-variant");
  const thumb = (on: boolean) => cn("grid size-14 place-items-center rounded-md bg-cover bg-center ring-offset-2 ring-offset-surface", on ? "ring-2 ring-primary" : "ring-1 ring-outline-variant");

  return (
    <div ref={wrap} className="absolute inset-0 bg-surface-lowest">
      <div ref={el} role="region" aria-label={ariaLabel} className="h-full w-full" />

      {/* Botón «Capas» como Google Maps */}
      <div className="no-print absolute bottom-6 left-4 z-10 flex flex-col items-start gap-2">
        {panel && (
          <div role="dialog" aria-label="Capas del mapa" className="max-h-[calc(100vh-22rem)] w-[340px] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-xl border border-outline-variant bg-surface p-4 shadow-2xl">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-display text-base font-bold">Tipo de mapa</span>
              <button type="button" aria-label="Cerrar capas" onClick={() => setPanel(false)} className="state-layer grid size-8 place-items-center rounded-full cursor-pointer"><Icon name="close" size={20} /></button>
            </div>
            <div className="grid grid-cols-4 gap-1" role="radiogroup" aria-label="Tipo de mapa">
              {(Object.keys(BASEMAPS) as BasemapId[]).map((id) => (
                <button key={id} type="button" role="radio" aria-checked={opts.base === id} title={BASEMAPS[id].detail} onClick={() => set("base", id)} className={chip(opts.base === id)}>
                  <span className={thumb(opts.base === id)} style={{ backgroundImage: BASEMAPS[id].thumb, backgroundColor: "#12291f" }} />
                  {BASEMAPS[id].label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-on-surface-muted">{BASEMAPS[opts.base].detail}</p>
            {baseError === opts.base && <p className="text-[11px] text-error" role="status">No se pudo cargar este fondo (¿sin internet?). Los datos se siguen viendo.</p>}
            <div className="mt-2 flex gap-4 text-[13px]">
              {([["Vista de globo", "globe"], ["Etiquetas", "labels"]] as const).map(([lab, k]) => (
                <label key={k} className="flex cursor-pointer items-center gap-2"><input type="checkbox" checked={opts[k]} onChange={(e) => set(k, e.target.checked)} className="size-4 accent-[var(--color-primary)]" />{lab}</label>
              ))}
            </div>

            <span className="mt-4 mb-2 block font-display text-base font-bold">Detalles del mapa</span>
            <div className="grid grid-cols-4 gap-1">
              {([["Relieve 3D", "landscape", opts.terrain, () => set("terrain", !opts.terrain)],
                ["Columnas 3D", "view_in_ar", opts.columns, () => set("columns", !opts.columns)],
                [`Cacao apto · ${nApt}`, "eco", opts.cacao, () => set("cacao", !opts.cacao)]] as const).map(([lab, ic, on, fn]) => (
                <button key={lab} type="button" aria-pressed={on} onClick={fn} className={chip(on)}>
                  <span className={cn(thumb(on), "bg-surface-high")}><Icon name={ic} size={26} /></span>{lab}
                </button>
              ))}
              {(Object.keys(OVERLAYS) as OverlayId[]).map((id) => {
                const on = opts.overlays.includes(id) && overlayState[id] !== "no";
                const st = overlayState[id];
                return (
                  <button key={id} type="button" aria-pressed={on} disabled={st === "cargando"} title={OVERLAYS[id].detail} onClick={() => toggleOverlay(id)} className={chip(on)}>
                    <span className={cn(thumb(on), "bg-surface-high")}><Icon name={st === "cargando" ? "hourglass_top" : OVERLAYS[id].icon} size={26} /></span>
                    {OVERLAYS[id].label}
                    {st === "no" && <span className="text-[10px] font-normal text-error">no disponible</span>}
                  </button>
                );
              })}
            </div>
            {opts.overlays.length > 0 && (
              <ul className="mt-2 flex flex-col gap-0.5 text-[11px] text-on-surface-muted">
                {opts.overlays.map((id) => <li key={id}>• {OVERLAYS[id].detail}</li>)}
              </ul>
            )}

            <span className="mt-4 mb-2 block font-display text-base font-bold">Herramientas del mapa</span>
            <div className="flex flex-wrap gap-2">
              <button type="button" aria-pressed={measuring} onClick={() => { setMeasuring((v) => !v); setMeasure([]); }}
                className={cn("state-layer inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold cursor-pointer", measuring ? "bg-secondary-container text-on-secondary-container" : "border border-outline")}>
                <Icon name="straighten" size={18} />{measuring ? "Terminar medición" : "Medir"}
              </button>
            </div>
          </div>
        )}
        <button type="button" onClick={() => setPanel((v) => !v)} aria-expanded={panel}
          className="group relative size-20 overflow-hidden rounded-xl border-2 border-white bg-cover bg-center shadow-lg cursor-pointer"
          style={{ backgroundImage: BASEMAPS[opts.base === "satelite" ? "predeterminado" : "satelite"].thumb, backgroundColor: "#12291f" }}>
          <span className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-1 bg-black/55 py-1 text-[12px] font-bold text-white">
            <Icon name="layers" size={16} />Capas
          </span>
        </button>
      </div>

      {/* Resultado de la medición */}
      {measuring && (
        <div role="status" className="no-print absolute bottom-6 left-1/2 z-10 -translate-x-1/2 rounded-full bg-surface-highest px-5 py-2.5 text-sm shadow-lg">
          {measure.length < 2 ? "Haga clic en el mapa para medir" : <>Distancia <b className="tabular">{distKm < 1 ? `${fmtInt(distKm * 1000)} m` : `${fmt1(distKm)} km`}</b>{areaHa > 0 && <> · Área <b className="tabular">{areaHa < 100 ? `${fmt1(areaHa)} ha` : `${fmtInt(areaHa)} ha`}</b></>}</>}
          {measure.length > 0 && <button type="button" onClick={() => setMeasure([])} className="ml-3 font-bold text-link cursor-pointer">Borrar</button>}
        </div>
      )}
    </div>
  );
}
