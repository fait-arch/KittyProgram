"use client";
import { useLossSummary } from "@/lib/api/hooks";
import type { Scenario, ScenarioId } from "@/lib/api/types";
import { LOSS_OUTLINE, LOSS_RAMP, RISK_CLASSES, RISK_LABEL } from "@/lib/design/colors";
import { fmtT, fmtUsd } from "@/lib/design/format";
import { Icon } from "@/components/ui/Icon";

/** Total del escenario (GET /losses/summary) + distribución de cantones por clase. */
export function SummaryCard({ scenario, province, scenarios }: { scenario: ScenarioId; province?: string; scenarios?: Scenario[] }) {
  const { data, error, isLoading } = useLossSummary(scenario, province);
  const sc = scenarios?.find((s) => s.id === scenario);
  return (
    <section aria-label="Resumen del escenario" aria-busy={isLoading} className="flex flex-col gap-3 rounded-lg bg-surface-high p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-on-surface-variant">Pérdida estimada · {province ?? "Costa"}</span>
      </div>
      {error ? (
        <p className="text-sm text-error">No se pudo cargar el resumen.</p>
      ) : !data ? (
        <div className="h-24 animate-pulse rounded-md bg-surface-highest" />
      ) : (
        <>
          <div className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1">
            <span className="font-display text-[44px] leading-[52px] font-black tabular">{fmtT(data.loss_t)}</span>
            <span className="font-display text-[22px] leading-7 font-bold text-on-surface-variant tabular">{fmtUsd(data.loss_usd)}</span>
          </div>
          <span className="text-sm text-on-surface-variant">
            {sc?.label ?? scenario} · {data.vs_normal ? `+${fmtT(data.vs_normal.loss_t)} frente a un año normal` : "línea base (años neutros)"}
          </span>
          {sc?.extrapolation && (
            <p className="flex items-start gap-2 rounded-md bg-surface-container p-3 text-[13px] leading-[18px]">
              <Icon name="warning" fill size={18} className="text-status-warn" />
              <span><b>Extrapolación:</b> clima fuera del rango con que se entrenó el modelo. Leer como tendencia.</span>
            </p>
          )}
          <div className="mt-1 flex flex-col gap-2">
            <span className="text-xs text-on-surface-variant">{data.n_areas} cantones por nivel de pérdida</span>
            <div role="img" aria-label={RISK_CLASSES.map((c) => `${RISK_LABEL[c]}: ${data.areas_by_class[c]}`).join(", ")} className="flex h-3 gap-0.5">
              {RISK_CLASSES.map((c, i) => (
                <div key={c} title={`${RISK_LABEL[c]}: ${data.areas_by_class[c]} cantones`} className="rounded-[3px]"
                  style={{ flex: `${data.areas_by_class[c]} 1 0px`, background: LOSS_RAMP[i], boxShadow: `inset 0 0 0 1px ${LOSS_OUTLINE}` }} />
              ))}
            </div>
            <div className="grid grid-cols-4 gap-1">
              {RISK_CLASSES.map((c) => (
                <div key={c} className="flex flex-col">
                  <span className="font-display text-base font-extrabold tabular">{data.areas_by_class[c]}</span>
                  <span className="text-[11px] leading-[14px] text-on-surface-variant">{RISK_LABEL[c]}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
