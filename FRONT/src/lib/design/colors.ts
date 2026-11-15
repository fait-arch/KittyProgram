/**
 * Colores de datos. Los mismos hex que qgis/estilos/*.qml, globals.css y docs/07-propuesta-ui.md.
 * Leaflet escribe atributos SVG (no acepta var(--…)), por eso aquí van como hex.
 *
 * Escala de pérdida: alerta de 5 niveles.
 *  - Colores de las fases IPC (FAO / FEWS NET): verde → amarillo → naranja → rojo → rojo oscuro.
 *  - Mismo semáforo que las alertas de la SNGR Ecuador (amarilla · naranja · roja).
 *  - El nivel 5 (Crítica) lleva rayado blanco a 45°, como "Famine likely" en FEWS NET,
 *    para que no dependa del color (rojo oscuro casi no contrasta con fondos oscuros).
 */
import type { RiskClass, Zone } from "@/lib/api/types";

export type Theme = "mision" | "campo";
export type LossLevel = 0 | 1 | 2 | 3 | 4;

export const LOSS_RAMP = ["#e8dc9a", "#d9b04f", "#c4722f", "#963a25", "#4a1a17"] as const;
/** Texto legible sobre cada color de la escala (contraste ≥ 4,5:1) */
export const LOSS_ON = ["#2b221c", "#2b221c", "#2b221c", "#ffffff", "#ffffff"] as const;
export const LOSS_OUTLINE = "#2b221c";
/** Nivel con rayado (Crítica). En el mapa se pinta con fill="url(#cr-hatch)". */
export const HATCH_LEVEL: LossLevel = 4;
export const HATCH_FILL = "url(#cr-hatch)";

export const RISK_CLASSES: RiskClass[] = ["baja", "moderada", "alta", "muy_alta", "critica"];
export const RISK_LABEL: Record<RiskClass, string> = {
  baja: "Baja",
  moderada: "Moderada",
  alta: "Alta",
  muy_alta: "Muy alta",
  critica: "Crítica",
};
export const RISK_RANGE = ["0 – 5", "5 – 15", "15 – 30", "30 – 45", "45 – 100"] as const;
/** Límites superiores (inclusivos) de cada clase, en % de pérdida */
export const RISK_BREAKS = [5, 15, 30, 45] as const;

/** Significado de cada nivel: ícono (nunca solo color), referencia IPC y alerta SNGR equivalente. */
export const RISK_META: Record<RiskClass, { icon: string; ipc: string; alert: string; meaning: string }> = {
  baja: { icon: "check_circle", ipc: "IPC 1", alert: "Sin alerta", meaning: "Pérdida dentro de lo habitual." },
  moderada: { icon: "info", ipc: "IPC 2", alert: "Alerta amarilla", meaning: "Vigilar: reforzar podas y remoción de mazorcas enfermas." },
  alta: { icon: "warning", ipc: "IPC 3", alert: "Alerta naranja", meaning: "Actuar: manejo sanitario y drenaje antes de las lluvias." },
  muy_alta: { icon: "error", ipc: "IPC 4", alert: "Alerta roja", meaning: "Pérdida grave: priorizar asistencia técnica." },
  critica: { icon: "dangerous", ipc: "IPC 5", alert: "Alerta roja · crítica", meaning: "Pérdida extrema: planificar reconversión o apoyo." },
};

/** Límite superior inclusivo, igual que el renderizador graduado de QGIS (5,0 % = Baja). */
export function lossClassIndex(pct: number): LossLevel {
  return pct <= 5 ? 0 : pct <= 15 ? 1 : pct <= 30 ? 2 : pct <= 45 ? 3 : 4;
}
export function riskClassOf(pct: number): RiskClass {
  return RISK_CLASSES[lossClassIndex(pct)];
}
export function riskLevel(c: RiskClass): LossLevel {
  return RISK_CLASSES.indexOf(c) as LossLevel;
}
/** Color plano del nivel (para gráficos y texto). */
export function lossColor(pct: number): string {
  return LOSS_RAMP[lossClassIndex(pct)];
}
/** Relleno para el mapa SVG: el nivel Crítico usa el patrón rayado. */
export function lossFill(pct: number): string {
  const i = lossClassIndex(pct);
  return i === HATCH_LEVEL ? HATCH_FILL : LOSS_RAMP[i];
}

export const ZONES: Zone[] = ["segura", "manejo", "transicion", "critica"];
export const ZONE_META: Record<Zone, { label: string; icon: string; quadrant: string; action: string }> = {
  segura: { label: "Segura", icon: "verified", quadrant: "aptitud alta · riesgo bajo", action: "Mantener y ampliar con buenas prácticas." },
  manejo: { label: "Manejo", icon: "handyman", quadrant: "aptitud alta · riesgo alto", action: "Invertir en manejo sanitario, drenaje y sombra." },
  transicion: { label: "Transición", icon: "swap_horiz", quadrant: "aptitud baja · riesgo bajo", action: "Diversificar: cacao bajo sombra, plátano o maderables." },
  critica: { label: "Crítica", icon: "report", quadrant: "aptitud baja · riesgo alto", action: "Evitar nuevas siembras; planificar reconversión con el MAG." },
};
/**
 * Semáforo de zonas (igual en ambos temas y en qgis/estilos/zonas_2050.qml).
 * "Segura" es verde azulado y no verde puro: con protanopía el verde se confunde con el amarillo.
 */
const ZONE_HEX: Record<Zone, string> = { segura: "#2f7f73", manejo: "#d9b04f", transicion: "#c4722f", critica: "#963a25" };
export const ZONE_COLORS: Record<Theme, Record<Zone, string>> = { mision: ZONE_HEX, campo: ZONE_HEX };
/** Texto legible sobre cada color de zona */
const ZONE_ON_HEX: Record<Zone, string> = { segura: "#ffffff", manejo: "#2b221c", transicion: "#2b221c", critica: "#ffffff" };
export const ZONE_ON: Record<Theme, Record<Zone, string>> = { mision: ZONE_ON_HEX, campo: ZONE_ON_HEX };

/** Colores del lienzo del mapa por tema */
export const MAP_THEME: Record<
  Theme,
  {
    context: string;
    contextStroke: string;
    outline: string;
    /** Selección: trazo + halo, para que se vea sobre cualquier nivel de la escala */
    selected: string;
    halo: string;
    graticule: string;
    noData: string;
    /** borde iluminado de las provincias que están en la base */
    province: string;
    north: string;
  }
> = {
  mision: { context: "#2b3b32", contextStroke: "#435a4d", outline: "#14201a", selected: "#ffffff", halo: "#14201a", graticule: "#24464a", noData: "#34463c", north: "#eceff1", province: "#dfe4dc" },
  campo: { context: "#e6e9e3", contextStroke: "#c3cbc1", outline: "#6e6656", selected: "#2b221c", halo: "#ffffff", graticule: "#b8cfc8", noData: "#d6dbd3", north: "#2b221c", province: "#4b3a2f" },
};

export const STATUS = {
  ok: { color: "var(--color-status-ok)", icon: "check_circle", label: "Dentro del óptimo" },
  warn: { color: "var(--color-status-warn)", icon: "warning", label: "Fuera del óptimo" },
  marginal: { color: "var(--color-status-marginal)", icon: "error", label: "Marginal" },
  out: { color: "var(--color-status-out)", icon: "dangerous", label: "Fuera del límite absoluto" },
} as const;
export type StatusKey = keyof typeof STATUS;
