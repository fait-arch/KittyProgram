"use client";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { useStoredBool } from "@/lib/uiPrefs";
import { Icon } from "@/components/atoms/Icon";
import { Badge } from "@/components/atoms/Badge";

export type NavKey = "panel" | "mapa" | "alertas" | "comparar" | "finca" | "plantillas" | "metodologia";
const ITEMS: { key: NavKey | "enso"; href: string; label: string; long: string; icon: string; badge?: string; mobile?: boolean }[] = [
  { key: "panel", href: "/panel", label: "Panel", long: "Panel general", icon: "dashboard", mobile: true },
  { key: "mapa", href: "/", label: "Mapa", long: "Mapa de pérdidas", icon: "map", mobile: true },
  { key: "alertas", href: "/alertas", label: "Alertas", long: "Alertas", icon: "notifications_active", mobile: true },
  { key: "comparar", href: "/comparar", label: "Comparar", long: "Comparar climas", icon: "compare", badge: "F2", mobile: true },
  { key: "finca", href: "/finca", label: "Mi finca", long: "Mi finca", icon: "agriculture", mobile: true },
  { key: "plantillas", href: "/plantillas", label: "Compartir", long: "Compartir e imprimir", icon: "ios_share" },
  { key: "enso", href: "/metodologia#enso", label: "El Niño", long: "¿Qué es El Niño?", icon: "waves" },
  { key: "metodologia", href: "/metodologia", label: "Método", long: "Método y fuentes", icon: "science" },
];

/**
 * Organismo · navegación lateral (patrón de la plantilla Harvest): en pantallas grandes, barra de 224 px con
 * ícono + nombre; en medianas, riel M3 de 80 px.
 */
export function NavRail({ active }: { active: NavKey }) {
  // Plegado: solo íconos en cualquier ancho. Se recuerda en este navegador.
  const [folded, setFolded] = useStoredBool("cr-menu-plegado");
  const wide = !folded; // en pantallas xl, con nombres largos
  return (
    <nav aria-label="Secciones" className={cn("hidden w-20 shrink-0 flex-col gap-1 border-r border-outline-variant bg-surface px-2 py-4 transition-[width] duration-300 lg:flex no-print", wide && "xl:w-56 xl:px-3")}>
      {ITEMS.map((it) => {
        const on = it.key === active;
        return (
          <Link key={it.key} href={it.href} aria-current={on ? "page" : undefined} title={it.long}
            className={cn("state-layer group relative flex flex-col items-center gap-1 rounded-lg px-1 py-2 text-xs transition-colors",
              wide && "xl:flex-row xl:gap-3 xl:px-3 xl:py-2.5 xl:text-sm",
              on ? "bg-secondary-container font-bold text-on-secondary-container" : "font-semibold text-on-surface-variant")}>
            <span className={cn("relative grid h-8 w-14 place-items-center rounded-full", wide && "xl:h-auto xl:w-auto", on && (wide ? "max-xl:bg-primary-container" : "bg-primary-container"))}>
              <Icon name={it.icon} fill={on} />
              {it.badge && <Badge size="xs" className={cn("absolute -top-1 -right-1", wide && "xl:hidden")}>{it.badge}</Badge>}
            </span>
            <span className={cn(wide && "xl:hidden")}>{it.label}</span>
            {wide && <span className="hidden flex-1 xl:inline">{it.long}</span>}
            {wide && it.badge && <Badge size="xs" className="hidden xl:inline-flex">{it.badge}</Badge>}
          </Link>
        );
      })}
      <button type="button" onClick={() => setFolded(!folded)} aria-pressed={folded}
        title={folded ? "Mostrar el menú con nombres" : "Plegar el menú (solo íconos)"}
        className={cn("state-layer mt-auto flex items-center justify-center gap-3 rounded-lg px-1 py-2 text-xs font-semibold text-on-surface-variant cursor-pointer", wide && "xl:justify-start xl:px-3 xl:text-sm")}>
        <Icon name={folded ? "left_panel_open" : "left_panel_close"} />
        <span className={cn("hidden", wide && "xl:inline")}>Plegar menú</span>
        <span className="sr-only">{folded ? "Mostrar el menú con nombres" : "Plegar el menú"}</span>
      </button>
    </nav>
  );
}

/** Barra de navegación M3 (móvil) */
export function NavBar({ active }: { active: NavKey }) {
  return (
    <nav aria-label="Secciones" className="fixed inset-x-0 bottom-0 z-[1100] flex h-20 bg-surface-container px-2 pt-3 pb-4 lg:hidden no-print">
      {ITEMS.filter((it) => it.mobile).map((it) => {
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
