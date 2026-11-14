"use client";
import { useMemo } from "react";
import type { AreaProps, LossItem } from "@/lib/api/types";
import { lossClassIndex } from "@/lib/design/colors";
import { Swatch } from "@/components/atoms/Swatch";
import { fmtPct } from "@/lib/design/format";
import { cn } from "@/lib/cn";

/** Los 5 cantones con mayor pérdida en el escenario (y provincia) elegidos. */
export function TopCantons({ items, areas, province, selectedId, onSelect }: {
  items?: LossItem[];
  areas: Map<string, AreaProps>;
  province?: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const top = useMemo(
    () => (items ?? []).filter((i) => !province || areas.get(i.area_id)?.province === province).sort((a, b) => b.loss_pct - a.loss_pct).slice(0, 5),
    [items, areas, province],
  );
  return (
    <section aria-label="Cantones con mayor pérdida" className="flex flex-col gap-2">
      <h2 className="font-display text-base font-bold">Cantones con mayor pérdida</h2>
      <ol className="flex flex-col gap-0.5">
        {top.map((t, i) => {
          const a = areas.get(t.area_id);
          return (
            <li key={t.area_id}>
              <button type="button" onClick={() => onSelect(t.area_id)} aria-current={t.area_id === selectedId ? "true" : undefined}
                className={cn("flex min-h-[52px] w-full items-center gap-3 rounded-md px-3 py-1.5 text-left cursor-pointer", t.area_id === selectedId ? "bg-surface-highest" : "hover:bg-surface-high")}>
                <span className="w-4 font-display text-sm font-bold text-on-surface-variant">{i + 1}</span>
                <span className="flex flex-1 flex-col">
                  <span className="text-[15px] font-semibold leading-5">{a?.name ?? t.area_id}</span>
                  <span className="text-xs text-on-surface-variant">{a?.province}</span>
                </span>
                <Swatch level={lossClassIndex(t.loss_pct)} size="sm" />
                <span className="min-w-16 text-right font-display text-base font-bold tabular">{fmtPct(t.loss_pct)}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
