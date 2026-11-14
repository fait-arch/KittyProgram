import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

/** Molécula · cifra + etiqueta (toneladas, USD, puntos frente a año normal). */
export function KpiTile({ value, label, icon, tone = "default", className }: {
  value: string;
  label: string;
  icon?: string;
  tone?: "default" | "alert" | "good";
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-0.5 rounded-md bg-surface-container p-3", className)}>
      <span
        className={cn(
          "flex items-center gap-1 font-display text-[22px] leading-7 font-extrabold tabular",
          tone === "alert" && "text-error",
          tone === "good" && "text-primary",
        )}
      >
        {icon && <Icon name={icon} size={22} />}
        {value}
      </span>
      <span className="text-xs text-on-surface-variant">{label}</span>
    </div>
  );
}
