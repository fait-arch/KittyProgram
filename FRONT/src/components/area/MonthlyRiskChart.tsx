"use client";
import { useState } from "react";
import type { MonthlyRisk } from "@/lib/api/types";
import { fmt2, MONTHS_NAME, MONTHS_SHORT } from "@/lib/design/format";

const H = 140;

/** Riesgo mensual por patógeno (0–1), barras agrupadas con tooltip. Época de lluvias sombreada. */
export function MonthlyRiskChart({ data }: { data: MonthlyRisk[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const peak = data.reduce((a, b) => (b.monilia > a.monilia ? b : a), data[0]);
  return (
    <section aria-label="Riesgo mes a mes" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="flex-1">
          <h2 className="font-display text-xl font-bold">Riesgo mes a mes</h2>
          <p className="text-[13px] text-on-surface-variant">Índice de clima favorable a la enfermedad (0 a 1)</p>
        </div>
        <Legend color="var(--color-series-monilia)" label="Moniliasis" />
        <Legend color="var(--color-series-phyto)" label="Mazorca negra" />
      </div>
      <div className="relative pl-7" role="img" aria-label={`Riesgo mensual; el mayor riesgo de moniliasis es en ${MONTHS_NAME[peak.month - 1]} (${fmt2(peak.monilia)}).`}>
        <div className="absolute top-0 left-7 h-[140px] w-1/2 bg-primary/8" />
        <span className="absolute top-1 left-9 text-[11px] text-on-surface-variant">Lluvias ene–jun</span>
        {[1, 0.5, 0].map((v) => (
          <div key={v}>
            <div className="absolute right-0 left-7 h-px" style={{ top: H - v * H, background: v === 0 ? "var(--color-outline)" : "var(--color-outline-variant)" }} />
            <span className="absolute left-0 text-[11px] text-on-surface-muted" style={{ top: H - v * H - 7 }}>{v === 0.5 ? "0,5" : v}</span>
          </div>
        ))}
        <div className="relative grid grid-cols-12" style={{ height: H + 26 }}>
          {data.map((m, i) => (
            <div key={m.month} className="flex flex-col items-center" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <div className="flex items-end justify-center gap-0.5" style={{ height: H }}>
                <div className="w-2.5 rounded-t" style={{ height: m.monilia * H, background: "var(--color-series-monilia)", opacity: hover == null || hover === i ? 1 : 0.45 }} />
                <div className="w-2.5 rounded-t" style={{ height: m.phytophthora * H, background: "var(--color-series-phyto)", opacity: hover == null || hover === i ? 1 : 0.45 }} />
              </div>
              <span className="mt-2 text-xs text-on-surface-variant">{MONTHS_SHORT[i]}</span>
            </div>
          ))}
          {hover != null && (
            <div className="pointer-events-none absolute -top-2 z-10 rounded-md bg-surface-highest px-3 py-2 text-xs shadow-lg"
              style={{ left: `calc(${((hover + 0.5) / 12) * 100}% - 70px)`, width: 140 }}>
              <b className="block">{MONTHS_NAME[hover]}</b>
              Moniliasis <b className="tabular">{fmt2(data[hover].monilia)}</b>
              <br />
              Mazorca negra <b className="tabular">{fmt2(data[hover].phytophthora)}</b>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px]">
      <span className="size-3 rounded-[3px]" style={{ background: color }} />
      {label}
    </span>
  );
}
