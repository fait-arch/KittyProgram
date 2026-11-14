"use client";
import { useMemo } from "react";
import type { AreaProps, LossItem } from "@/lib/api/types";
import { fmtPct, fmtPctRange, fmtT, fmtUsd } from "@/lib/design/format";
import { Dialog } from "@/components/molecules/Dialog";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";

/** Organismo · "Ver como tabla": la misma información del mapa, accesible por teclado y lector de pantalla. */
export function LossTable({ open, onClose, items, areas, scenarioLabel, onSelect }: {
  open: boolean;
  onClose: () => void;
  items: LossItem[];
  areas: Map<string, AreaProps>;
  scenarioLabel: string;
  onSelect: (id: string) => void;
}) {
  const rows = useMemo(() => [...items].sort((a, b) => b.loss_pct - a.loss_pct), [items]);
  return (
    <Dialog open={open} onClose={onClose} title={`Pérdida por cantón · ${scenarioLabel}`} icon="table_rows">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Pérdida estimada de cacao por cantón, ordenada de mayor a menor</caption>
        <thead className="sticky top-0 bg-surface-high text-left text-xs uppercase tracking-wide text-on-surface-variant">
          <tr>
            <th className="py-2 pr-3">Cantón</th>
            <th className="py-2 pr-3">Provincia</th>
            <th className="py-2 pr-3 text-right">Pérdida</th>
            <th className="py-2 pr-3">Rango</th>
            <th className="py-2 pr-3">Clase</th>
            <th className="py-2 pr-3 text-right">t</th>
            <th className="py-2 text-right">USD</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const a = areas.get(r.area_id);
            return (
              <tr key={r.area_id} className="border-t border-outline-variant">
                <td className="py-1.5 pr-3">
                  <button type="button" className="font-semibold text-link hover:underline cursor-pointer" onClick={() => onSelect(r.area_id)}>
                    {a?.name ?? r.area_id}
                  </button>
                </td>
                <td className="py-1.5 pr-3 text-on-surface-variant">{a?.province}</td>
                <td className="py-1.5 pr-3 text-right font-display font-bold tabular">{fmtPct(r.loss_pct)}</td>
                <td className="py-1.5 pr-3 tabular text-on-surface-variant">{fmtPctRange(r.loss_pct_low, r.loss_pct_high)}</td>
                <td className="py-1.5 pr-3">
                  <AlertLevelChip risk={r.risk_class} size="sm" />
                </td>
                <td className="py-1.5 pr-3 text-right tabular">{fmtT(r.loss_t)}</td>
                <td className="py-1.5 text-right tabular">{fmtUsd(r.loss_usd)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Dialog>
  );
}
