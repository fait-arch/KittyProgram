import { cn } from "@/lib/cn";

/** Ícono de Material Symbols Rounded. Decorativo por defecto (aria-hidden). */
export function Icon({ name, fill, size = 24, className, label }: { name: string; fill?: boolean; size?: number; className?: string; label?: string }) {
  return (
    <span
      className={cn("ms", fill && "ms-fill", className)}
      style={{ fontSize: size }}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {name}
    </span>
  );
}
