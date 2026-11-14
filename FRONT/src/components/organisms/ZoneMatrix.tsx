import type { Zone } from "@/lib/api/types";
import { ZONE_COLORS, ZONE_META, ZONE_ON, type Theme } from "@/lib/design/colors";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

/** Matriz 2×2: aptitud climática 2050 (filas) × riesgo de enfermedad (columnas). */
export function ZoneMatrix({ counts, theme, highlight, highlightName }: { counts?: Record<Zone, number>; theme: Theme; highlight?: Zone; highlightName?: string }) {
  const cell = (z: Zone) => (
    <article key={z} className={cn("flex flex-col gap-2 rounded-lg border bg-surface-low p-4", highlight === z ? "border-cta" : "border-outline-variant")}>
      <div className="flex items-center gap-2.5">
        <span className="grid size-9 place-items-center rounded-[10px]" style={{ background: ZONE_COLORS[theme][z], color: ZONE_ON[theme][z] }}>
          <Icon name={ZONE_META[z].icon} fill size={20} />
        </span>
        <span className="flex-1 font-display text-lg font-extrabold">{ZONE_META[z].label}</span>
        <span className="font-display text-[22px] font-extrabold tabular">{counts?.[z] ?? "–"}</span>
      </div>
      <span className="text-sm leading-5">{ZONE_META[z].action}{highlight === z && highlightName ? ` Aquí está ${highlightName}.` : ""}</span>
    </article>
  );
  return (
    <div className="grid grid-cols-[24px_repeat(2,minmax(0,1fr))] gap-3">
      <span />
      <span className="text-center text-[13px] font-semibold text-on-surface-variant">Riesgo de enfermedad <b className="text-on-surface">bajo</b></span>
      <span className="text-center text-[13px] font-semibold text-on-surface-variant">Riesgo de enfermedad <b className="text-on-surface">alto</b></span>
      <span className="rotate-180 text-center text-[13px] font-semibold text-on-surface-variant [writing-mode:vertical-rl]">Aptitud 2050 <b className="text-on-surface">alta</b></span>
      {cell("segura")}
      {cell("manejo")}
      <span className="rotate-180 text-center text-[13px] font-semibold text-on-surface-variant [writing-mode:vertical-rl]">Aptitud 2050 <b className="text-on-surface">baja</b></span>
      {cell("transicion")}
      {cell("critica")}
    </div>
  );
}
