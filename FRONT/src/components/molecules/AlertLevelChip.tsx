import type { RiskClass } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { RISK_LABEL, RISK_META, riskLevel } from "@/lib/design/colors";
import { Icon } from "@/components/atoms/Icon";
import { Swatch } from "@/components/atoms/Swatch";

/**
 * Molécula · nivel de alerta de pérdida: muestra + ícono + texto (nunca solo color).
 * `detail` agrega la equivalencia IPC / SNGR para quien la conoce.
 */
export function AlertLevelChip({ risk, size = "md", prefix, detail, className }: {
  risk: RiskClass;
  size?: "sm" | "md";
  prefix?: string;
  detail?: boolean;
  className?: string;
}) {
  const m = RISK_META[risk];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap",
        size === "md" ? "h-8 rounded-sm bg-surface-container px-3 text-sm font-bold" : "text-sm",
        className,
      )}
    >
      <Swatch level={riskLevel(risk)} size={size === "md" ? "sm" : "sm"} />
      {size === "md" && <Icon name={m.icon} fill size={16} className="text-on-surface-variant" />}
      <span>{prefix ? `${prefix} ${RISK_LABEL[risk].toLowerCase()}` : RISK_LABEL[risk]}</span>
      {detail && <span className="font-normal text-on-surface-variant">· {m.alert}</span>}
    </span>
  );
}
