import type { AreaDetail } from "@/lib/api/types";
import { LOSS_OUTLINE, lossColor, RISK_LABEL } from "@/lib/design/colors";
import { fmtPct, fmtPctRange, fmtPts, fmtT, fmtUsd } from "@/lib/design/format";
import { Icon } from "@/components/ui/Icon";

/** Cifra principal + rango probable (p10–p90) + toneladas, USD y diferencia con año normal. */
export function LossHero({ d, scenarioLabel }: { d: AreaDetail; scenarioLabel: string }) {
  const l = d.loss;
  const max = Math.max(50, Math.ceil(l.loss_pct_high / 10) * 10);
  const x = (v: number) => `${(v / max) * 100}%`;
  const color = lossColor(l.loss_pct);
  return (
    <section aria-label="Pérdida estimada" className="flex flex-col gap-4 rounded-lg bg-surface-high p-5">
      <span className="text-sm font-semibold text-on-surface-variant">Pérdida estimada de producción · {scenarioLabel}</span>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="font-display text-[57px] leading-[64px] font-black tabular">{fmtPct(l.loss_pct)}</span>
        <span className="inline-flex h-8 items-center gap-1.5 rounded-sm bg-surface-container px-3 text-sm font-bold">
          <span className="size-3 rounded-[3px]" style={{ background: color, boxShadow: `inset 0 0 0 1px ${LOSS_OUTLINE}` }} />
          Pérdida {RISK_LABEL[l.risk_class].toLowerCase()}
        </span>
      </div>
      <div className="flex flex-col gap-1.5">
        <div role="img" aria-label={`Rango probable entre ${fmtPctRange(l.loss_pct_low, l.loss_pct_high)}; estimación central ${fmtPct(l.loss_pct)}`} className="relative h-6">
          <div className="absolute inset-x-0 top-[9px] h-1.5 rounded-full bg-outline-variant" />
          <div className="absolute top-1.5 h-3 rounded-full opacity-50" style={{ left: x(l.loss_pct_low), width: `calc(${x(l.loss_pct_high)} - ${x(l.loss_pct_low)})`, background: color }} />
          <div className="absolute top-[3px] size-[18px] -ml-[9px] rounded-full ring-2 ring-surface-high" style={{ left: x(l.loss_pct), background: color, boxShadow: `0 0 0 3px ${LOSS_OUTLINE}33` }} />
        </div>
        <div className="flex justify-between text-[11px] text-on-surface-muted tabular"><span>0 %</span><span>{max / 2} %</span><span>{max} %</span></div>
        <span className="text-[13px] leading-[18px]">Rango probable (p10–p90): <b>{fmtPctRange(l.loss_pct_low, l.loss_pct_high)}</b>. Ocho de cada diez temporadas similares caen aquí.</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Kpi value={fmtT(l.loss_t)} label="grano seco perdido" />
        <Kpi value={fmtUsd(l.loss_usd)} label="valor en riesgo" />
        {l.vs_normal ? (
          <Kpi value={fmtPts(l.vs_normal.delta_pct).replace(" pts", "")} label={`puntos frente a un año normal (${fmtPct(l.vs_normal.loss_pct)})`} icon={l.vs_normal.delta_pct >= 0 ? "trending_up" : "trending_down"} accent />
        ) : (
          <Kpi value="Base" label="escenario de referencia" />
        )}
      </div>
    </section>
  );
}

function Kpi({ value, label, icon, accent }: { value: string; label: string; icon?: string; accent?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-surface-container p-3">
      <span className={`flex items-center gap-1 font-display text-[22px] leading-7 font-extrabold tabular ${accent ? "text-error" : ""}`}>
        {icon && <Icon name={icon} size={22} />}
        {value}
      </span>
      <span className="text-xs text-on-surface-variant">{label}</span>
    </div>
  );
}
