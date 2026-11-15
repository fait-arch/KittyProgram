/**
 * Geometría de la finca en el navegador (sin dependencias).
 * Coordenadas [lon, lat] en grados WGS 84, como GeoJSON.
 */
export type LonLat = [number, number];
const R = 6371008.8; // radio medio de la Tierra (m)
const rad = (d: number) => (d * Math.PI) / 180;

/** Área geodésica de un anillo (m²), fórmula de Chamberlain & Duquette (la misma idea que turf/area). */
export function ringAreaM2(ring: LonLat[]): number {
  const n = ring.length;
  if (n < 3) return 0;
  let s = 0;
  for (let i = 0; i < n; i++) {
    const [l1, p1] = ring[i];
    const [l2, p2] = ring[(i + 1) % n];
    s += rad(l2 - l1) * (2 + Math.sin(rad(p1)) + Math.sin(rad(p2)));
  }
  return Math.abs((s * R * R) / 2);
}
export const ringAreaHa = (ring: LonLat[]) => ringAreaM2(ring) / 10_000;

/** Centroide del polígono (plano; suficiente para fincas de pocas hectáreas). */
export function ringCentroid(ring: LonLat[]): LonLat {
  if (ring.length < 3) return ring[0] ?? [0, 0];
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    const f = x1 * y2 - x2 * y1;
    a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-14) return ring[0];
  return [cx / (3 * a), cy / (3 * a)];
}

/** Punto en anillo (ray casting) */
function inRing(pt: LonLat, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
/** Punto en Polygon / MultiPolygon de GeoJSON (respeta huecos) */
export function pointInGeometry(pt: LonLat, g: { type: string; coordinates: unknown }): boolean {
  const polys = (g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : []) as number[][][][];
  return polys.some((rings) => inRing(pt, rings[0]) && !rings.slice(1).some((h) => inRing(pt, h)));
}

/** ¿Se cruzan los lados? (un polígono que se corta a sí mismo da un área sin sentido) */
export function selfIntersects(ring: LonLat[]): boolean {
  const n = ring.length;
  const cross = (a: LonLat, b: LonLat, c: LonLat) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const hit = (p1: LonLat, p2: LonLat, p3: LonLat, p4: LonLat) =>
    cross(p3, p4, p1) * cross(p3, p4, p2) < 0 && cross(p1, p2, p3) * cross(p1, p2, p4) < 0;
  for (let i = 0; i < n; i++)
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      if (hit(ring[i], ring[(i + 1) % n], ring[j], ring[(j + 1) % n])) return true;
    }
  return false;
}
