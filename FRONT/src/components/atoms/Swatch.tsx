import { cn } from "@/lib/cn";
import { HATCH_LEVEL, LOSS_OUTLINE, LOSS_RAMP, type LossLevel } from "@/lib/design/colors";

/**
 * Átomo · muestra de color de la leyenda (como el símbolo de una capa en QGIS).
 * Con `level` pinta la escala de alerta; el nivel Crítico lleva rayado (.hatch-critica).
 * Decorativo: el texto que lo acompaña siempre nombra la clase.
 */
export function Swatch({ level, color, size = "md", className }: {
  level?: LossLevel;
  color?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const hatch = level === HATCH_LEVEL;
  const bg = color ?? (level != null ? LOSS_RAMP[level] : undefined);
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block shrink-0 rounded-[3px]",
        size === "sm" && "h-3 w-3",
        size === "md" && "h-3.5 w-5",
        size === "lg" && "h-5 w-5 rounded-[4px]",
        hatch && "hatch-critica",
        className,
      )}
      style={{ background: hatch ? undefined : bg, boxShadow: `inset 0 0 0 1px ${LOSS_OUTLINE}` }}
    />
  );
}
