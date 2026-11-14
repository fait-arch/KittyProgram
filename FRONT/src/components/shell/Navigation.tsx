import Link from "next/link";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

export type NavKey = "mapa" | "comparar" | "metodologia";
const ITEMS: { key: NavKey | "enso"; href: string; label: string; icon: string; badge?: string }[] = [
  { key: "mapa", href: "/", label: "Mapa", icon: "map" },
  { key: "comparar", href: "/comparar", label: "Comparar", icon: "compare", badge: "F2" },
  { key: "enso", href: "/metodologia#enso", label: "El Niño", icon: "waves" },
  { key: "metodologia", href: "/metodologia", label: "Método", icon: "science" },
];

/** Riel de navegación M3 (escritorio) */
export function NavRail({ active }: { active: NavKey }) {
  return (
    <nav aria-label="Secciones" className="hidden w-20 shrink-0 flex-col items-center gap-3 border-r border-outline-variant bg-surface py-4 lg:flex no-print">
      {ITEMS.map((it) => {
        const on = it.key === active;
        return (
          <Link key={it.key} href={it.href} aria-current={on ? "page" : undefined}
            className={cn("flex flex-col items-center gap-1 text-xs", on ? "font-bold text-on-surface" : "font-semibold text-on-surface-variant")}>
            <span className={cn("relative grid h-8 w-14 place-items-center rounded-full", on ? "bg-secondary-container text-on-secondary-container" : "hover:bg-on-surface/8")}>
              <Icon name={it.icon} fill={on} />
              {it.badge && <span className="absolute -top-0.5 right-1.5 rounded-full bg-neon-yellow px-1 font-display text-[10px] font-extrabold leading-[14px] text-deep-blue">{it.badge}</span>}
            </span>
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Barra de navegación M3 (móvil) */
export function NavBar({ active }: { active: NavKey }) {
  return (
    <nav aria-label="Secciones" className="fixed inset-x-0 bottom-0 z-[1100] flex h-20 bg-surface-container px-2 pt-3 pb-4 lg:hidden no-print">
      {ITEMS.map((it) => {
        const on = it.key === active;
        return (
          <Link key={it.key} href={it.href} aria-current={on ? "page" : undefined}
            className={cn("flex flex-1 flex-col items-center gap-1 text-xs", on ? "font-bold text-on-surface" : "font-semibold text-on-surface-variant")}>
            <span className={cn("grid h-8 w-16 place-items-center rounded-full", on && "bg-secondary-container text-on-secondary-container")}>
              <Icon name={it.icon} fill={on} />
            </span>
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}
