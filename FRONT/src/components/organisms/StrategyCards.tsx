"use client";
import { useState } from "react";
import type { StrategiesResponse, Strategy } from "@/lib/api/types";
import { fmtPct, fmtT, fmtUsd } from "@/lib/design/format";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/atoms/Icon";

const TABS: { key: keyof Pick<Strategy, "why" | "evidence" | "data_gaps" | "risks">; label: string }[] = [
  { key: "why", label: "Por qué" },
  { key: "evidence", label: "Evidencia" },
  { key: "data_gaps", label: "Datos que faltan" },
  { key: "risks", label: "Riesgos" },
];

/** "¿Qué hacer?": estrategias ordenadas por pérdida evitada (GET /areas/{id}/strategies). */
export function StrategyCards({ data }: { data: StrategiesResponse }) {
  const [open, setOpen] = useState<string | null>(data.items[0]?.id ?? null);
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("why");
  return (
    <section aria-label="Qué hacer" className="flex flex-col gap-3">
      <div>
        <h2 className="font-display text-xl font-bold">¿Qué hacer?</h2>
        <p className="text-[13px] text-on-surface-variant">Ordenadas por la pérdida que evitan · línea base: manejo actual, {fmtPct(data.baseline_loss_pct)}</p>
      </div>
      {[...data.items].sort((a, b) => a.rank - b.rank).map((s) => {
        const isOpen = open === s.id;
        return (
          <article key={s.id} className={cn("flex flex-col gap-3 rounded-lg border p-4", isOpen ? "border-primary bg-surface-container" : "border-outline-variant")}>
            <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : s.id)} className="flex items-start gap-3.5 text-left cursor-pointer">
              <span className={cn("grid size-8 shrink-0 place-items-center rounded-full font-display text-base font-black", s.rank === 1 ? "bg-cta text-on-cta" : "bg-secondary-container text-on-secondary-container")}>{s.rank}</span>
              <span className="flex flex-1 flex-col gap-0.5">
                <span className="font-display text-[17px] leading-6 font-bold">{s.name}</span>
                <span className="text-[13px] leading-[18px] text-on-surface-variant">{s.summary}</span>
              </span>
              <span className="flex flex-col items-end">
                {s.protects_income ? (
                  <>
                    <span className="font-display text-base font-extrabold">Protege</span>
                    <span className="text-xs text-on-surface-variant">el ingreso total</span>
                  </>
                ) : (
                  <>
                    <span className="font-display text-lg font-extrabold tabular">{fmtUsd(s.avoided_loss_usd)}</span>
                    <span className="text-xs text-on-surface-variant">evitada ≈ {fmtT(s.avoided_loss_t)}</span>
                  </>
                )}
              </span>
              <Icon name={isOpen ? "expand_less" : "expand_more"} className="text-on-surface-variant" />
            </button>
            {isOpen && (
              <>
                <div role="tablist" aria-label={`Detalle de ${s.name}`} className="flex flex-wrap gap-2">
                  {TABS.map((t) => (
                    <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
                      className={cn("h-8 rounded-sm px-3 text-[13px] font-semibold cursor-pointer", tab === t.key ? "bg-secondary-container text-on-secondary-container" : "border border-outline text-on-surface-variant")}>
                      {t.label}
                    </button>
                  ))}
                </div>
                <p role="tabpanel" className="text-sm leading-[21px]">{s[tab]}</p>
                {!s.protects_income && <p className="text-xs text-on-surface-muted">Pérdida esperada con esta estrategia: {fmtPct(s.expected_loss_pct)}</p>}
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}
