import type { CompareItem, Scenario } from "@/lib/api/types";
import { fmtPct, fmtPctRange } from "@/lib/design/format";

const H = 180;

/** Estimación central y rango p10–p90 por escenario (un solo tono, sin líneas que unan categorías). */
export function LossRangeChart({ items, scenarios }: { items: CompareItem[]; scenarios?: Scenario[] }) {
  const max = Math.max(60, Math.ceil(Math.max(...items.map((i) => i.loss.loss_pct_high)) / 20) * 20);
  const y = (v: number) => H - (v / max) * H;
  const ticks = Array.from({ length: max / 20 + 1 }, (_, i) => i * 20);
  const label = (id: string) => scenarios?.find((s) => s.id === id)?.label ?? id;
  return (
    <div role="img" aria-label={items.map((i) => `${label(i.scenario)}: ${fmtPct(i.loss.loss_pct)}`).join("; ")} className="relative pl-10" style={{ height: H + 30 }}>
      {ticks.map((t) => (
        <div key={t}>
          <div className="absolute right-0 left-10 h-px" style={{ top: y(t), background: t === 0 ? "var(--color-outline)" : "var(--color-outline-variant)" }} />
          <span className="absolute left-0 text-[11px] text-on-surface-muted" style={{ top: y(t) - 7 }}>{t} %</span>
        </div>
      ))}
      <div className="relative grid h-full" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((i) => (
          <div key={i.scenario} className="relative" title={`${label(i.scenario)}: ${fmtPct(i.loss.loss_pct)} (rango ${fmtPctRange(i.loss.loss_pct_low, i.loss.loss_pct_high)})`}>
            <div className="absolute left-1/2 -ml-px w-0.5 rounded bg-primary" style={{ top: y(i.loss.loss_pct_high), height: y(i.loss.loss_pct_low) - y(i.loss.loss_pct_high) }} />
            <div className="absolute left-1/2 -mt-2 -ml-2 size-4 rounded-full bg-primary ring-[3px] ring-surface" style={{ top: y(i.loss.loss_pct) }} />
            <span className="absolute left-1/2 ml-3.5 -mt-2.5 font-display text-[15px] font-extrabold tabular" style={{ top: y(i.loss.loss_pct) }}>{fmtPct(i.loss.loss_pct)}</span>
            <span className="absolute inset-x-0 text-center text-xs text-on-surface-variant" style={{ top: H + 8 }}>{label(i.scenario)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
