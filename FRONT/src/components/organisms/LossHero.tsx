import type { AreaDetail } from "@/lib/api/types";
import { RISK_META } from "@/lib/design/colors";
import { fmtPct, fmtPctRange, fmtPts, fmtT, fmtUsd } from "@/lib/design/format";
import { Icon } from "@/components/atoms/Icon";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";
import { KpiTile } from "@/components/molecules/KpiTile";
import { LossInterval } from "@/components/molecules/LossInterval";

/** Chips del modelo: estimación por zona, extrapolación y probabilidad de año malo. */
export function ModelChips({ l }: { l: NonNullable<AreaDetail["loss"]> }) {
  const chip = "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold leading-[18px]";
  return (
    <div className="flex flex-wrap gap-2">
      {l.evidence === "indice_subnacional_no_validado" && (
        <span className={`${chip} bg-surface-container text-on-surface`} title="El modelo se valida a nivel nacional; por zona es un índice de riesgo, no una predicción exacta.">
          <Icon name="travel_explore" size={16} /> Estimación por zona{l.inherited_from ? ` · índice de ${l.inherited_from}` : ""}
        </span>
      )}
      {l.evidence === "validado_nacional" && (
        <span className={`${chip} bg-primary-container text-on-primary-container`}><Icon name="verified" size={16} /> Validado a nivel nacional</span>
      )}
      {l.extrapolated && (
        <span className={`${chip} bg-surface-container text-on-surface`} title="El clima de este escenario es más extremo que cualquier año con que se entrenó el modelo.">
          <Icon name="warning" size={16} /> Extrapolación: leer como tendencia
        </span>
      )}
      {l.prob_loss_gt20 != null && (
        <span className={`${chip} ${l.prob_loss_gt20 >= 0.5 ? "bg-error-container text-on-error-container" : "bg-surface-container text-on-surface"}`}>
          <Icon name="casino" size={16} /> {Math.round(l.prob_loss_gt20 * 100)} % de probabilidad de perder más del 20 %
        </span>
      )}
    </div>
  );
}

/** Organismo · cifra principal + rango probable (p10–p90) + toneladas, USD y diferencia con año normal. */
export function LossHero({ d, scenarioLabel }: { d: AreaDetail; scenarioLabel: string }) {
  const l = d.loss;
  if (!l) {
    return (
      <section aria-label="Pérdida estimada" className="flex flex-col gap-2 rounded-lg bg-surface-high p-5">
        <span className="text-sm font-semibold text-on-surface-variant">Pérdida estimada de producción · {scenarioLabel}</span>
        <p className="flex gap-2 text-[15px] leading-[22px]">
          <Icon name="info" size={20} className="text-primary" />
          El modelo todavía no tiene estimación para {d.area.name} en este escenario. Se entrena con la producción de las provincias de la Costa; abajo están el clima y el riesgo de enfermedad del cantón.
        </p>
      </section>
    );
  }
  return (
    <section aria-label="Pérdida estimada" className="flex flex-col gap-4 rounded-lg bg-surface-high p-5">
      <span className="text-sm font-semibold text-on-surface-variant">Pérdida estimada de producción · {scenarioLabel}</span>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="font-display text-[57px] leading-[64px] font-black tabular">{fmtPct(l.loss_pct)}</span>
        <AlertLevelChip risk={l.risk_class} prefix="Pérdida" />
      </div>
      <p className="-mt-2 text-[13px] leading-[18px] text-on-surface-variant">{RISK_META[l.risk_class].alert} · {RISK_META[l.risk_class].meaning}</p>
      <ModelChips l={l} />
      <div className="flex flex-col gap-1.5">
        <LossInterval low={l.loss_pct_low} mid={l.loss_pct} high={l.loss_pct_high} />
        <span className="text-[13px] leading-[18px]">Rango probable (p10–p90): <b>{fmtPctRange(l.loss_pct_low, l.loss_pct_high)}</b>. Ocho de cada diez temporadas similares caen aquí.</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {l.loss_t != null ? <KpiTile value={fmtT(l.loss_t)} label="grano seco perdido" />
          : <KpiTile value="—" label="toneladas: sin hectáreas medidas en el cantón" />}
        {l.loss_usd != null ? <KpiTile value={fmtUsd(l.loss_usd)} label="valor en riesgo" />
          : <KpiTile value="—" label="valor: se calcula por provincia" />}
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
