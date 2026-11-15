"use client";
/**
 * Mapa coroplético con Leaflet (sin teselas: fondo sólido, funciona sin internet).
 * Organismo · patrón QGIS: símbolo graduado (alerta de 5 niveles), borde fino, grilla, norte y escala.
 * Nivel Crítico: relleno "url(#cr-hatch)" (atoms/HatchDefs). Selección: halo + trazo en una capa aparte.
 * Se carga con next/dynamic({ ssr: false }).
 */
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useRef } from "react";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { AreaProps, AreasGeoJSON, Zone } from "@/lib/api/types";
import { lossFill, MAP_THEME, ZONE_COLORS, type Theme } from "@/lib/design/colors";
import { Icon } from "@/components/atoms/Icon";

export interface LossMapProps {
  areas?: AreasGeoJSON;
  context?: FeatureCollection;
  /** Provincias de la base: se dibujan con un borde iluminado encima de los cantones */
  provinces?: FeatureCollection;
  mode: "perdida" | "zonas";
  values?: Map<string, number>;
  zones?: Map<string, Zone>;
  selectedId?: string | null;
  dimProvince?: string;
  onSelect?: (id: string) => void;
  tooltip?: (p: AreaProps) => string;
  theme: Theme;
  decorations?: boolean;
  focus?: "all" | "selected";
  interactive?: boolean;
  attribution?: string;
  ariaLabel: string;
  className?: string;
}

export default function LossMap(props: LossMapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.GeoJSON | null>(null);
  const ctx = useRef<L.GeoJSON | null>(null);
  const provLayer = useRef<L.GeoJSON | null>(null);
  const sel = useRef<L.LayerGroup | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const { interactive = true, decorations = true } = props;

  // 1. Crear el mapa una vez
  useEffect(() => {
    if (!el.current) return;
    const m = L.map(el.current, {
      zoomControl: false,
      zoomSnap: 0.25,
      attributionControl: true,
      dragging: interactive,
      scrollWheelZoom: interactive,
      doubleClickZoom: interactive,
      touchZoom: interactive,
      boxZoom: false,
      keyboard: interactive,
    }).setView([-1.4, -79.6], 7);
    m.attributionControl.setPrefix(false);
    m.createPane("contexto").style.zIndex = "350";
    m.createPane("grilla").style.zIndex = "360";
    const pp = m.createPane("provincias");
    pp.style.zIndex = "430";
    pp.style.pointerEvents = "none";
    const sp = m.createPane("seleccion");
    sp.style.zIndex = "450";
    sp.style.pointerEvents = "none";

    if (decorations) {
      L.control.scale({ imperial: false, position: "bottomright", maxWidth: 140 }).addTo(m);
      const North = L.Control.extend({
        onAdd() {
          const d = L.DomUtil.create("div");
          d.setAttribute("role", "img");
          d.setAttribute("aria-label", "Norte");
          d.innerHTML = `<svg width="28" height="40" viewBox="-14 -26 28 40"><path d="M0 -22 L9 8 L0 2 L-9 8 Z" fill="currentColor"/><path d="M0 -22 L0 2 L-9 8 Z" fill="currentColor" opacity=".45"/><text x="0" y="13" text-anchor="middle" font-family="Fira Sans" font-weight="800" font-size="11" fill="currentColor">N</text></svg>`;
          d.style.color = MAP_THEME[latest.current.theme].north;
          d.className = "cr-north";
          return d;
        },
      });
      new North({ position: "bottomright" }).addTo(m);
      // Grilla de coordenadas cada 1° (como en una composición de QGIS)
      const g = L.layerGroup([], { pane: "grilla" });
      for (let lon = -81; lon <= -75; lon++) {
        L.polyline([[2, lon], [-5.5, lon]], { pane: "grilla", interactive: false, weight: 1, dashArray: "3 4", className: "cr-grat" }).addTo(g);
        L.marker([1.75, lon], { pane: "grilla", interactive: false, keyboard: false, icon: L.divIcon({ className: "cr-grat-label", html: `${Math.abs(lon)}°O`, iconSize: [36, 12], iconAnchor: [18, 6] }) }).addTo(g);
      }
      for (let lat = 1; lat >= -5; lat--) {
        L.polyline([[lat, -81.6], [lat, -74.8]], { pane: "grilla", interactive: false, weight: 1, dashArray: "3 4", className: "cr-grat" }).addTo(g);
        const lab = lat === 0 ? "0°" : `${Math.abs(lat)}°${lat > 0 ? "N" : "S"}`;
        L.marker([lat, -75.15], { pane: "grilla", interactive: false, keyboard: false, icon: L.divIcon({ className: "cr-grat-label", html: lab, iconSize: [28, 12], iconAnchor: [14, 14] }) }).addTo(g);
      }
      g.addTo(m);
    }

    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    map.current = m;
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      layer.current = null;
      ctx.current = null;
      sel.current = null;
    };
  }, [interactive, decorations]);

  // 2. Capa de contexto (Sierra y Amazonía, fuera del alcance de la Fase 1)
  useEffect(() => {
    const m = map.current;
    if (!m || !props.context) return;
    ctx.current?.remove();
    ctx.current = L.geoJSON(props.context, { pane: "contexto", interactive: false, style: () => ctxStyle(latest.current.theme) }).addTo(m);
  }, [props.context]);

  // 2b. Límites de provincia de la base, iluminados
  useEffect(() => {
    const m = map.current;
    if (!m || !props.provinces) return;
    provLayer.current?.remove();
    provLayer.current = L.geoJSON(props.provinces, { pane: "provincias", interactive: false, style: () => provStyle(latest.current.theme) }).addTo(m);
  }, [props.provinces]);

  // 3. Cantones
  useEffect(() => {
    const m = map.current;
    if (!m || !props.areas) return;
    layer.current?.remove();
    const gj = L.geoJSON(props.areas as FeatureCollection<Geometry, AreaProps>, {
      style: (f) => styleFor(f as Feature<Geometry, AreaProps>, latest.current),
      onEachFeature: (f, l) => {
        const p = (f as Feature<Geometry, AreaProps>).properties;
        l.on("click", () => latest.current.onSelect?.(p.id));
        if (latest.current.tooltip) {
          l.bindTooltip(() => latest.current.tooltip!(p), { sticky: true, direction: "top", offset: [0, -10], className: "cr-tooltip" });
        }
      },
    }).addTo(m);
    layer.current = gj;
    // Solo si hay geometrías válidas (un área sin polígono deja los límites vacíos)
    const sz = m.getSize();
    if (props.focus !== "selected" && gj.getBounds().isValid() && sz.x > 0 && sz.y > 0) {
      try { m.fitBounds(gj.getBounds(), { padding: [16, 16] }); } catch { /* contenedor aún sin medidas */ }
    }
    if (props.attribution) m.attributionControl.addAttribution(props.attribution);
    return () => {
      if (props.attribution) m.attributionControl.removeAttribution(props.attribution);
    };
  }, [props.areas, props.attribution, props.focus]);

  // 4. Estilo según escenario, capa, selección y tema
  useEffect(() => {
    const gj = layer.current;
    if (!gj) return;
    gj.setStyle((f) => styleFor(f as Feature<Geometry, AreaProps>, latest.current));
    ctx.current?.setStyle(() => ctxStyle(props.theme));
    provLayer.current?.setStyle(() => provStyle(props.theme));
    const north = map.current?.getContainer().querySelector<HTMLElement>(".cr-north");
    if (north) north.style.color = MAP_THEME[props.theme].north;
    map.current?.getPane("grilla")?.style.setProperty("--grat", MAP_THEME[props.theme].graticule);
    sel.current?.remove();
    sel.current = null;
    if (props.selectedId && map.current) {
      gj.eachLayer((l) => {
        const f = (l as L.Path & { feature?: Feature<Geometry, AreaProps> }).feature;
        if (f?.properties.id === props.selectedId) {
          const t = MAP_THEME[props.theme];
          // Halo ancho + trazo fino: visible sobre verde menta y sobre rojo oscuro por igual
          const opts = { pane: "seleccion", interactive: false, fill: false } as const;
          sel.current = L.layerGroup([
            L.geoJSON(f, { ...opts, style: { color: t.halo, weight: 6, opacity: 0.9, lineJoin: "round" } }),
            L.geoJSON(f, { ...opts, style: { color: t.selected, weight: 2.5, opacity: 1, lineJoin: "round" } }),
          ]).addTo(map.current!);
          if (props.focus === "selected" && (l as L.Polygon).getBounds().isValid() && (map.current?.getSize().x ?? 0) > 0) { try { map.current?.fitBounds((l as L.Polygon).getBounds().pad(1.6), { animate: false }); } catch { /* sin medidas */ } }
        }
      });
    }
  }, [props.values, props.zones, props.mode, props.selectedId, props.theme, props.dimProvince, props.focus, props.areas]);

  return (
    <div className={props.className ?? "absolute inset-0"}>
      <div ref={el} role="region" aria-label={props.ariaLabel} className="h-full w-full" />
      {interactive && decorations && (
        <div className="absolute top-4 right-4 z-[800] flex flex-col gap-2 no-print">
          <div className="flex flex-col overflow-hidden rounded-md bg-surface-high shadow">
            <button type="button" aria-label="Acercar" onClick={() => map.current?.zoomIn()} className="grid size-12 place-items-center text-on-surface hover:bg-surface-highest cursor-pointer"><Icon name="add" /></button>
            <button type="button" aria-label="Alejar" onClick={() => map.current?.zoomOut()} className="grid size-12 place-items-center border-t border-outline-variant text-on-surface hover:bg-surface-highest cursor-pointer"><Icon name="remove" /></button>
          </div>
          <button type="button" aria-label="Ver todo el mapa" onClick={() => layer.current?.getBounds().isValid() && map.current?.fitBounds(layer.current.getBounds(), { padding: [16, 16] })} className="grid size-12 place-items-center rounded-md bg-surface-high text-on-surface shadow hover:bg-surface-highest cursor-pointer"><Icon name="zoom_out_map" /></button>
        </div>
      )}
    </div>
  );
}

function provStyle(theme: Theme): L.PathOptions {
  return { fill: false, color: MAP_THEME[theme].province, weight: 1.6, opacity: 0.9, lineJoin: "round" };
}

function ctxStyle(theme: Theme): L.PathOptions {
  const t = MAP_THEME[theme];
  return { fillColor: t.context, fillOpacity: 1, color: t.contextStroke, weight: 0.8 };
}

function styleFor(f: Feature<Geometry, AreaProps>, p: LossMapProps): L.PathOptions {
  const t = MAP_THEME[p.theme];
  const id = f.properties.id;
  let fill = t.noData;
  if (p.mode === "perdida") {
    const v = p.values?.get(id);
    if (v != null) fill = lossFill(v);
  } else {
    const z = p.zones?.get(id);
    if (z) fill = ZONE_COLORS[p.theme][z];
  }
  const dim = !!p.dimProvince && f.properties.province !== p.dimProvince;
  return { fillColor: fill, fillOpacity: dim ? 0.25 : 1, color: t.outline, weight: 0.7, opacity: dim ? 0.5 : 1 };
}
