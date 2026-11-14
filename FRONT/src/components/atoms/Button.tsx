import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

/**
 * Átomo · botones M3. "filled" es la acción clave (verde cacao en ambos temas): máximo uno por pantalla.
 * Textura: brillo superior + borde interior + elevación 1 (.tex-filled); capa de estado M3 (.state-layer)
 * en vez de brightness(), para que hover/presionado se vean igual sobre cualquier color.
 */
export type ButtonVariant = "filled" | "tonal" | "outlined" | "text";

const base =
  "state-layer inline-flex items-center justify-center gap-2 rounded-full font-sans text-sm font-bold leading-5 transition-shadow disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none cursor-pointer whitespace-nowrap";
const variants: Record<ButtonVariant, string> = {
  filled: "tex-filled bg-cta text-on-cta h-10 pl-4 pr-5",
  tonal: "tex-tonal bg-secondary-container text-on-secondary-container h-10 pl-4 pr-5",
  outlined: "border border-outline text-on-surface h-10 pl-4 pr-5",
  text: "text-link h-10 px-3",
};

type Common = { variant?: ButtonVariant; icon?: string; trailingIcon?: string; children: ReactNode; className?: string };

export function Button({ variant = "tonal", icon, trailingIcon, children, className, ...rest }: Common & Omit<ComponentProps<"button">, "children">) {
  return (
    <button type="button" className={cn(base, variants[variant], className)} {...rest}>
      {icon && <Icon name={icon} size={18} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={18} />}
    </button>
  );
}

export function LinkButton({ variant = "tonal", icon, trailingIcon, children, className, href, ...rest }: Common & { href: string } & Omit<ComponentProps<"a">, "href" | "children">) {
  return (
    <Link href={href} className={cn(base, variants[variant], className)} {...rest}>
      {icon && <Icon name={icon} size={18} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={18} />}
    </Link>
  );
}

/** Botón de ícono (48×48, área táctil M3) */
export function IconButton({ icon, label, className, fill, ...rest }: { icon: string; label: string; fill?: boolean } & Omit<ComponentProps<"button">, "children">) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn("state-layer grid size-12 place-items-center rounded-full text-on-surface-variant cursor-pointer", className)}
      {...rest}
    >
      <Icon name={icon} fill={fill} />
    </button>
  );
}
