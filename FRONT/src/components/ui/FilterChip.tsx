import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

/** Chip de filtro M3 (capas del mapa, provincias, capas a exportar). */
export function FilterChip({ selected, children, className, icon, ...rest }: { selected: boolean; icon?: string } & ComponentProps<"button">) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-sm text-sm font-semibold whitespace-nowrap cursor-pointer",
        selected ? "bg-secondary-container pl-2 pr-4 text-on-secondary-container" : "border border-outline px-4 text-on-surface-variant hover:bg-on-surface/5",
        className,
      )}
      {...rest}
    >
      {selected ? <Icon name="check" size={18} /> : icon ? <Icon name={icon} size={18} /> : null}
      {children}
    </button>
  );
}
