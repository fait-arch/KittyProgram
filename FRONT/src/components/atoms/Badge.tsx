import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Átomo · etiqueta corta (FASE 2, RECOMENDADO, F2).
 * "highlight" usa Neon Yellow de Space Apps sobre Deep Blue: el único lugar donde queda el amarillo de marca.
 */
export function Badge({ tone = "highlight", size = "md", children, className }: {
  tone?: "highlight" | "primary" | "neutral";
  size?: "xs" | "md";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-display font-extrabold tracking-normal whitespace-nowrap",
        size === "xs" ? "px-1 text-[10px] leading-[14px]" : "px-1.5 text-[10px] leading-4",
        tone === "highlight" && "bg-[#c9bd7e] text-[#2b221c]",
        tone === "primary" && "bg-primary-container text-on-primary-container",
        tone === "neutral" && "bg-surface-highest text-on-surface-variant",
        className,
      )}
    >
      {children}
    </span>
  );
}
