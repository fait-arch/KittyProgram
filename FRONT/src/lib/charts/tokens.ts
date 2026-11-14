"use client";
/**
 * Tokens de color para gráficos. ECharts dibuja en <canvas> y no entiende var(--…),
 * así que se leen los valores reales de globals.css cada vez que cambia el tema.
 * Una sola fuente de verdad: globals.css (y qgis/estilos para la escala de pérdida).
 */
import { useEffect, useState } from "react";
import { useTheme } from "@/lib/theme";

const KEYS = [
  "on-surface", "on-surface-variant", "on-surface-muted", "outline", "outline-variant",
  "surface", "surface-high", "surface-highest", "primary", "primary-container", "error",
  "series-monilia", "series-phyto", "loss-0", "loss-1", "loss-2", "loss-3", "loss-4", "loss-outline",
] as const;
export type ChartTokens = Record<(typeof KEYS)[number], string> & { font: string; display: string; reducedMotion: boolean };

const FALLBACK: ChartTokens = {
  "on-surface": "#edf4ee", "on-surface-variant": "#bcc8bd", "on-surface-muted": "#9da89e", outline: "#667768", "outline-variant": "#1f2d20",
  surface: "#081109", "surface-high": "#122014", "surface-highest": "#18271a", primary: "#64bd5b", "primary-container": "#085630", error: "#ff8a6b",
  "series-monilia": "#2e96f5", "series-phyto": "#d95926", "loss-0": "#b2ffd8", "loss-1": "#fae61e", "loss-2": "#e67800", "loss-3": "#c80000", "loss-4": "#640000",
  "loss-outline": "#232323", font: "Overpass, system-ui, sans-serif", display: "'Fira Sans', system-ui, sans-serif", reducedMotion: false,
};

function read(): ChartTokens {
  const cs = getComputedStyle(document.documentElement);
  const out = { ...FALLBACK };
  for (const k of KEYS) {
    const v = cs.getPropertyValue(`--color-${k}`).trim();
    if (v) out[k] = v;
  }
  out.font = cs.getPropertyValue("--font-sans").trim() || FALLBACK.font;
  out.display = cs.getPropertyValue("--font-display").trim() || FALLBACK.display;
  out.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return out;
}

export function useChartTokens(): ChartTokens {
  const { theme } = useTheme();
  const [t, setT] = useState<ChartTokens>(FALLBACK);
  // El tema cambia <html data-theme>; se relee después de aplicarlo
  useEffect(() => {
    const id = requestAnimationFrame(() => setT(read()));
    return () => cancelAnimationFrame(id);
  }, [theme]);
  return t;
}

/** Opciones comunes: texto con tokens de texto, ejes y grilla recesivos, tooltip M3. */
export function baseOption(t: ChartTokens) {
  return {
    animation: !t.reducedMotion,
    animationDuration: 500,
    textStyle: { fontFamily: t.font, color: t["on-surface-variant"] },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      backgroundColor: t["surface-highest"],
      borderWidth: 0,
      padding: [8, 12],
      textStyle: { color: t["on-surface"], fontFamily: t.font, fontSize: 13 },
      extraCssText: "border-radius:12px;box-shadow:0 4px 12px rgb(0 0 0 / .35);",
    },
    axisCommon: {
      axisLine: { lineStyle: { color: t.outline } },
      axisTick: { show: false },
      axisLabel: { color: t["on-surface-muted"], fontSize: 11 },
      splitLine: { lineStyle: { color: t["outline-variant"], type: "dashed" as const } },
    },
  };
}

/** Patrón rayado del nivel Crítico (decal de ECharts = LinePatternFill de QGIS) */
export const HATCH_DECAL = {
  symbol: "rect",
  symbolSize: 1,
  rotation: -Math.PI / 4,
  dashArrayX: [1, 0],
  dashArrayY: [2, 4],
  color: "rgba(255,255,255,0.7)",
} as const;
