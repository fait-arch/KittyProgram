import type { RiskClass } from "@/lib/api/types";
import { RISK_CLASSES, RISK_LABEL } from "@/lib/design/colors";
import { cn } from "@/lib/cn";

/**
 * Molécula · cuántos cantones caen en cada nivel de alerta.
 * Barra apilada (separación de 2 px entre segmentos) + conteos con texto.
 */
export function ClassDistribution({ counts, total }: { counts: Record<RiskClass, number>; total: number }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs text-on-surface-variant">{total} cantones por nivel de pérdida</span>
      <div role="img" aria-label={RISK_CLASSES.map((c) => `${RISK_LABEL[c]}: ${counts[c]}`).join(", ")} className="flex h-3 gap-0.5">
        {RISK_CLASSES.map((c, i) =>
          counts[c] ? (
            <div key={c} title={`${RISK_LABEL[c]}: ${counts[c]} cantones`}
              className={cn("rounded-[3px]", i === 4 && "hatch-critica")}
              style={{ flex: `${counts[c]} 1 0px`, background: i === 4 ? undefined : `var(--color-loss-${i})`, boxShadow: "inset 0 0 0 1px #232323" }} />
          ) : null,
        )}
      </div>
      <div className="grid grid-cols-5 gap-1">
        {RISK_CLASSES.map((c) => (
          <div key={c} className={cn("flex flex-col", !counts[c] && "opacity-50")}>
            <span className="font-display text-base font-extrabold tabular">{counts[c]}</span>
            <span className="text-[11px] leading-[14px] text-on-surface-variant">{RISK_LABEL[c]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
