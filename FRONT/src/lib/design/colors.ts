/**
 * Colores de datos. Los mismos hex que qgis/estilos/*.qml y docs/07-propuesta-ui.md.
 * Leaflet escribe atributos SVG (no acepta var(--…)), por eso aquí van como hex.
 */
import type { RiskClass, Zone } from "@/lib/api/types";

export type Theme = "mision" | "campo";

/** ColorBrewer YlOrRd · 4 clases (patrón de símbolo graduado de QGIS) */
export const LOSS_RAMP = ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"] as const;
export const LOSS_OUTLINE = "#232323";
export const RISK_CLASSES: RiskClass[] = ["baja", "moderada", "alta", "muy_alta"];
export const RISK_LABEL: Record<RiskClass, string> = {
  baja: "Baja",
  moderada: "Moderada",
  alta: "Alta",
  muy_alta: "Muy alta",
};
export const RISK_RANGE = ["0 – 5", "5 – 15", "15 – 30", "30 – 100"] as const;

/** Límite superior inclusivo, igual que el renderizador graduado de QGIS (5,0 % = Baja). */
export function lossClassIndex(pct: number): 0 | 1 | 2 | 3 {
  return pct <= 5 ? 0 : pct <= 15 ? 1 : pct <= 30 ? 2 : 3;
}
export function riskClassOf(pct: number): RiskClass {
  return RISK_CLASSES[lossClassIndex(pct)];
}
export function lossColor(pct: number): string {
  return LOSS_RAMP[lossClassIndex(pct)];
}

export const ZONES: Zone[] = ["segura", "manejo", "transicion", "critica"];
export const ZONE_META: Record<Zone, { label: string; icon: string; quadrant: string; action: string }> = {
  segura: { label: "Segura", icon: "verified", quadrant: "aptitud alta · riesgo bajo", action: "Mantener y ampliar con buenas prácticas." },
  manejo: { label: "Manejo", icon: "handyman", quadrant: "aptitud alta · riesgo alto", action: "Invertir en manejo sanitario, drenaje y sombra." },
  transicion: { label: "Transición", icon: "swap_horiz", quadrant: "aptitud baja · riesgo bajo", action: "Diversificar: cacao bajo sombra, plátano o maderables." },
  critica: { label: "Crítica", icon: "report", quadrant: "aptitud baja · riesgo alto", action: "Evitar nuevas siembras; planificar reconversión con el MAG." },
};
export const ZONE_COLORS: Record<Theme, Record<Zone, string>> = {
  mision: { segura: "#2e96f5", manejo: "#315a97", transicion: "#994920", critica: "#fb784f" },
  campo: { segura: "#0760e1", manejo: "#9dc1ee", transicion: "#f0ad7f", critica: "#e43700" },
};
/** Texto legible sobre cada color de zona */
export const ZONE_ON: Record<Theme, Record<Zone, string>> = {
  mision: { segura: "#04122f", manejo: "#ffffff", transicion: "#ffffff", critica: "#07173f" },
  campo: { segura: "#ffffff", manejo: "#07173f", transicion: "#07173f", critica: "#ffffff" },
};

/** Colores del lienzo del mapa por tema */
export const MAP_THEME: Record<
  Theme,
  { context: string; contextStroke: string; outline: string; selected: string; graticule: string; noData: string; north: string }
> = {
  mision: { context: "#0e2252", contextStroke: "#2a3f72", outline: "#040c24", selected: "#ffffff", graticule: "#2a3f72", noData: "#1a3268", north: "#eaf0ff" },
  campo: { context: "#dfe5f1", contextStroke: "#c3cce0", outline: LOSS_OUTLINE, selected: "#0042a6", graticule: "#c3cce0", noData: "#dfe5f1", north: "#07173f" },
};

export const STATUS = {
  ok: { color: "var(--color-status-ok)", icon: "check_circle", label: "Dentro del óptimo" },
  warn: { color: "var(--color-status-warn)", icon: "warning", label: "Fuera del óptimo" },
  marginal: { color: "var(--color-status-marginal)", icon: "error", label: "Marginal" },
  out: { color: "var(--color-status-out)", icon: "dangerous", label: "Fuera del límite absoluto" },
} as const;
export type StatusKey = keyof typeof STATUS;
