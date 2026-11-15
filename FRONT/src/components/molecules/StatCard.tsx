import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";
import { Skeleton } from "@/components/atoms/Skeleton";

/**
 * Molécula · tarjeta de indicador (patrón StatCard de la plantilla Harvest): ícono en recuadro verde suave,
 * tendencia arriba a la derecha, cifra grande y nombre. Sube = malo para pérdidas (rojo), por eso `trendBad`.
 */
export function StatCard({ icon, value, label, trend, trendBad = true, foot, loading }: {
  icon: string;
  value: ReactNode;
  label: string;
  trend?: { value: string; up: boolean } | null;
  trendBad?: boolean;
  foot?: string;
  loading?: boolean;
}) {
  const bad = trend ? trend.up === trendBad : false;
  return (
    <div className="lift flex flex-col gap-4 rounded-xl border border-outline-variant bg-surface-lowest p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="grid size-11 place-items-center rounded-lg bg-primary/12 text-primary"><Icon name={icon} size={24} /></span>
        {trend && (
          <span className={cn("inline-flex items-center gap-1 text-sm font-bold", bad ? "text-error" : "text-primary")}>
            <Icon name={trend.up ? "trending_up" : "trending_down"} size={18} />{trend.value}
          </span>
        )}
      </div>
      {loading ? <Skeleton className="h-14" /> : (
        <div>
          <p className="font-display text-[28px] font-extrabold leading-8 tabular">{value}</p>
          <p className="text-sm text-on-surface-variant">{label}</p>
          {foot && <p className="mt-1 text-xs text-on-surface-muted">{foot}</p>}
        </div>
      )}
    </div>
  );
}

/** Molécula · tarjeta base del panel (Card de la plantilla) */
export function PanelCard({ title, icon, action, children, className }: { title: string; icon?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section aria-label={title} className={cn("flex flex-col gap-4 rounded-xl border border-outline-variant bg-surface-lowest p-5 shadow-sm", className)}>
      <div className="flex items-center gap-2">
        {icon && <span className="grid size-8 place-items-center rounded-lg bg-primary/12 text-primary"><Icon name={icon} size={18} /></span>}
        <h2 className="flex-1 font-display text-lg font-bold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
