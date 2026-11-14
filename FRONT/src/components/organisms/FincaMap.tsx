"use client";
/**
 * Organismo · mapa para dibujar la finca (Leaflet, sin teselas).
 * Clic = agrega un vértice; los vértices se pueden arrastrar. Debajo, los cantones con su nivel de alerta
 * (transparentes) para ubicarse. Alternativa sin mouse: GPS o coordenadas en el panel.
 */
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useRef } from "react";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { AreaProps, AreasGeoJSON } from "@/lib/api/types";
import { lossFill, MAP_THEME, type Theme } from "@/lib/design/colors";
import type { LonLat } from "@/lib/geo/finca";
import { Icon } from "@/components/atoms/Icon";

export default function FincaMap({ areas, context, values, points, onChange, drawing, theme, focusCanton, accent }: {
  areas?: AreasGeoJSON;
  context?: FeatureCollection;
  values?: Map<string, number>;
  points: LonLat[];
  onChange: (p: LonLat[]) => void;
  drawing: boolean;
  theme: Theme;
  focusCanton?: string | null;
  /** Color del polígono (hex): el primario del tema */
  accent: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const base = useRef<L.GeoJSON | null>(null);
  const ctx = useRef<L.GeoJSON | null>(null);
  const draw = useRef<L.LayerGroup | null>(null);
  const latest = useRef({ points, onChange, drawing });
  latest.current = { points, onChange, drawing };

  useEffect(() => {
    if (!el.current) return;
    const m = L.map(el.current, { zoomControl: false, zoomSnap: 0.25, doubleClickZoom: false, attributionControl: true }).setView([-1.4, -79.6], 7);
    m.attributionControl.setPrefix(false);
    m.createPane("contexto").style.zIndex = "350";
    L.control.scale({ imperial: false, position: "bottomright", maxWidth: 140 }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => {
      const { points: p, onChange: cb, drawing: d } = latest.current;
      if (!d) return;
      cb([...p, [Math.round(e.latlng.lng * 1e6) / 1e6, Math.round(e.latlng.lat * 1e6) / 1e6]]);
    });
    draw.current = L.layerGroup().addTo(m);
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    map.current = m;
    return () => { ro.disconnect(); m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !context) return;
    ctx.current?.remove();
    const t = MAP_THEME[theme];
    ctx.current = L.geoJSON(context, { pane: "contexto", interactive: false, style: { fillColor: t.context, fillOpacity: 1, color: t.contextStroke, weight: 0.8 } }).addTo(m);
  }, [context, theme]);

  // Cantones de referencia (nivel de alerta, semitransparentes)
  useEffect(() => {
    const m = map.current;
    if (!m || !areas) return;
    base.current?.remove();
    const t = MAP_THEME[theme];
    base.current = L.geoJSON(areas as FeatureCollection<Geometry, AreaProps>, {
      interactive: false,
      style: (f) => {
        const p = (f as Feature<Geometry, AreaProps>).properties;
        const v = values?.get(p.id);
        const on = p.id === focusCanton;
        return { fillColor: v != null ? lossFill(v) : t.noData, fillOpacity: on ? 0.55 : 0.3, color: on ? t.selected : t.outline, weight: on ? 2 : 0.6, opacity: 0.8 };
      },
    }).addTo(m);
    base.current.bringToBack();
    if (!latest.current.points.length) m.fitBounds(base.current.getBounds(), { padding: [16, 16] });
  }, [areas, values, theme, focusCanton]);

  // Polígono y vértices
  useEffect(() => {
    const g = draw.current;
    if (!g) return;
    g.clearLayers();
    const ll = points.map(([x, y]) => L.latLng(y, x));
    const halo = MAP_THEME[theme].halo;
    if (ll.length >= 3) L.polygon(ll, { color: accent, weight: 3, fillColor: accent, fillOpacity: 0.25, interactive: false }).addTo(g);
    else if (ll.length === 2) L.polyline(ll, { color: accent, weight: 3, dashArray: "6 6", interactive: false }).addTo(g);
    ll.forEach((p, i) => {
      const mk = L.marker(p, {
        draggable: true, keyboard: false, title: `Vértice ${i + 1}`,
        icon: L.divIcon({ className: "", iconSize: [18, 18], iconAnchor: [9, 9],
          html: `<span style="display:block;width:18px;height:18px;border-radius:50%;background:${accent};border:3px solid ${halo};box-shadow:0 1px 3px rgb(0 0 0/.4)"></span>` }),
      });
      mk.on("dragend", () => {
        const q = mk.getLatLng();
        const next = [...latest.current.points];
        next[i] = [Math.round(q.lng * 1e6) / 1e6, Math.round(q.lat * 1e6) / 1e6];
        latest.current.onChange(next);
      });
      mk.addTo(g);
    });
  }, [points, accent, theme]);

  // Al cargar una finca (URL, GPS o guardada), acercar a ella
  const prevLen = useRef(0);
  useEffect(() => {
    const m = map.current;
    if (m && points.length && (prevLen.current === 0 || Math.abs(points.length - prevLen.current) > 1)) {
      const b = L.latLngBounds(points.map(([x, y]) => L.latLng(y, x)));
      if (points.length === 1) m.setView(b.getCenter(), 12); else m.fitBounds(b.pad(6), { maxZoom: 14 });
    }
    prevLen.current = points.length;
  }, [points]);

  return (
    <div className="absolute inset-0">
      <div ref={el} role="application" aria-label="Mapa para dibujar la finca: haga clic para agregar vértices" className="h-full w-full" style={{ cursor: drawing ? "crosshair" : undefined }} />
      <div className="absolute top-4 right-4 z-[800] flex flex-col overflow-hidden rounded-md bg-surface-high shadow no-print">
        <button type="button" aria-label="Acercar" onClick={() => map.current?.zoomIn()} className="state-layer grid size-12 place-items-center text-on-surface cursor-pointer"><Icon name="add" /></button>
        <button type="button" aria-label="Alejar" onClick={() => map.current?.zoomOut()} className="state-layer grid size-12 place-items-center border-t border-outline-variant text-on-surface cursor-pointer"><Icon name="remove" /></button>
      </div>
    </div>
  );
}
