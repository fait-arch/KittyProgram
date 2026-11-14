import type { AreaDetail } from "@/lib/api/types";
import { RISK_META } from "@/lib/design/colors";
import { fmtPct, fmtPctRange, fmtPts, fmtT, fmtUsd } from "@/lib/design/format";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";
import { KpiTile } from "@/components/molecules/KpiTile";
import { LossInterval } from "@/components/molecules/LossInterval";

/** Organismo · cifra principal + rango probable (p10–p90) + toneladas, USD y diferencia con año normal. */
export function LossHero({ d, scenarioLabel }: { d: AreaDetail; scenarioLabel: string }) {
  const l = d.loss;
  return (
    <section aria-label="Pérdida estimada" className="flex flex-col gap-4 rounded-lg bg-surface-high p-5">
      <span className="text-sm font-semibold text-on-surface-variant">Pérdida estimada de producción · {scenarioLabel}</span>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="font-display text-[57px] leading-[64px] font-black tabular">{fmtPct(l.loss_pct)}</span>
        <AlertLevelChip risk={l.risk_class} prefix="Pérdida" />
      </div>
      <p className="-mt-2 text-[13px] leading-[18px] text-on-surface-variant">{RISK_META[l.risk_class].alert} · {RISK_META[l.risk_class].meaning}</p>
      <div className="flex flex-col gap-1.5">
        <LossInterval low={l.loss_pct_low} mid={l.loss_pct} high={l.loss_pct_high} />
        <span className="text-[13px] leading-[18px]">Rango probable (p10–p90): <b>{fmtPctRange(l.loss_pct_low, l.loss_pct_high)}</b>. Ocho de cada diez temporadas similares caen aquí.</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <KpiTile value={fmtT(l.loss_t)} label="grano seco perdido" />
        <KpiTile value={fmtUsd(l.loss_usd)} label="valor en riesgo" />
        {l.vs_normal ? (
          <KpiTile value={fmtPts(l.vs_normal.delta_pct).replace(" pts", "")} label={`puntos frente a un año normal (${fmtPct(l.vs_normal.loss_pct)})`}
            icon={l.vs_normal.delta_pct >= 0 ? "trending_up" : "trending_down"} tone={l.vs_normal.delta_pct >= 0 ? "alert" : "good"} />
        ) : (
          <KpiTile value="Base" label="escenario de referencia" />
        )}
      </div>
    </section>
  );
}

