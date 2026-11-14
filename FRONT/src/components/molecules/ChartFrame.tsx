"use client";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

export type LegendEntry = { label: string; color?: string; swatch?: ReactNode; dashed?: boolean };

/**
 * Molécula · marco común de los gráficos: título, subtítulo, leyenda siempre visible
 * y botón "Ver como tabla" (la misma información sin depender del color ni del canvas).
 */
export function ChartFrame({ title, subtitle, legend, table, children, className, level = 2 }: {
  title: string;
  subtitle?: string;
  legend?: LegendEntry[];
  table: ReactNode;
  children: ReactNode;
  className?: string;
  level?: 2 | 3;
}) {
  const [asTable, setAsTable] = useState(false);
  const H = level === 2 ? "h2" : "h3";
  return (
    <section aria-label={title} className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <H className="font-display text-xl font-bold">{title}</H>
          {subtitle && <p className="text-[13px] text-on-surface-variant">{subtitle}</p>}
        </div>
        <button type="button" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}
          className="state-layer inline-flex h-8 items-center gap-1.5 rounded-sm border border-outline px-3 text-[13px] font-semibold text-on-surface-variant cursor-pointer">
          <Icon name={asTable ? "monitoring" : "table_rows"} size={18} />
          {asTable ? "Ver gráfico" : "Ver como tabla"}
        </button>
      </div>
      {legend && legend.length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Leyenda">
          {legend.map((l) => (
            <li key={l.label} className="inline-flex items-center gap-1.5 text-[13px]">
              {l.swatch ?? (
                <span className={cn("inline-block h-[3px] w-4 rounded-full", l.dashed && "bg-transparent border-t-2 border-dashed")}
                  style={l.dashed ? { borderColor: l.color } : { background: l.color }} />
              )}
              {l.label}
            </li>
          ))}
        </ul>
      )}
      {asTable ? <div className="overflow-x-auto rounded-md border border-outline-variant">{table}</div> : children}
    </section>
  );
}

/** Tabla simple para la vista accesible de un gráfico */
export function ChartTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="bg-surface-high text-left text-xs uppercase tracking-wide text-on-surface-variant">
        <tr>{head.map((h, i) => <th key={h} className={cn("px-3 py-2", i > 0 && "text-right")}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, j) => (
          <tr key={j} className="border-t border-outline-variant">
            {r.map((c, i) => <td key={i} className={cn("px-3 py-1.5", i > 0 && "text-right tabular")}>{c}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
