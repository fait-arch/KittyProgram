"use client";
/**
 * Asesoría por WhatsApp (Fase 2). Número de atención: 0964213841 → +593 96 421 3841.
 * Si la persona ya consultó un cantón, el chat se abre con un mensaje que lleva esa consulta,
 * así el asesor no tiene que preguntar de nuevo (wa.me abre directo la conversación).
 */
import { useSyncExternalStore } from "react";

export const WA_NUMBER = "593964213841";
export const WA_DISPLAY = "096 421 3841";

export interface Consulta {
  /** "canton" o "provincia" (alertas) */
  tipo: "canton" | "provincia";
  nombre: string;
  provincia?: string | null;
  escenario: string;
  perdidaPct?: number | null;
  rango?: [number | null, number | null];
  nivel?: string | null;
  url?: string;
}

const KEY = "cr-ultima-consulta";
const listeners = new Set<() => void>();
let cache: { raw: string | null; value: Consulta | null } = { raw: null, value: null };

function read(): Consulta | null {
  let raw: string | null = null;
  try { raw = sessionStorage.getItem(KEY); } catch { /* sin almacenamiento */ }
  if (raw !== cache.raw) cache = { raw, value: raw ? (JSON.parse(raw) as Consulta) : null };
  return cache.value;
}

/** Guarda la última consulta concreta (ficha de cantón, alerta de provincia). */
export function rememberConsulta(c: Consulta) {
  try { sessionStorage.setItem(KEY, JSON.stringify(c)); } catch { /* */ }
  listeners.forEach((l) => l());
}

export function useUltimaConsulta(): Consulta | null {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    read,
    () => null,
  );
}

const pct = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1).replace(".", ",")} %`);

/** Texto del primer mensaje: genérico o con la consulta concreta. */
export function waMessage(c?: Consulta | null): string {
  if (!c) return "Hola, estoy usando CacaoResiliente y quisiera asesoría sobre el riesgo de El Niño para mi cacao.";
  const lugar = c.tipo === "canton" ? `el cantón ${c.nombre}${c.provincia ? ` (${c.provincia})` : ""}` : `la provincia ${c.nombre}`;
  const cifra = c.perdidaPct != null
    ? ` La app estima una pérdida de ${pct(c.perdidaPct)}${c.rango && c.rango[0] != null ? ` (rango ${pct(c.rango[0])}–${pct(c.rango[1])})` : ""}${c.nivel ? `, nivel ${c.nivel.toLowerCase()}` : ""}.`
    : "";
  return `Hola, consulté en CacaoResiliente ${lugar} en el escenario «${c.escenario}».${cifra} Quisiera asesoría sobre qué hacer en mi finca.${c.url ? `\n${c.url}` : ""}`;
}

export const waLink = (c?: Consulta | null) => `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(waMessage(c))}`;
