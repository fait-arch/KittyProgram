"use client";
import dynamic from "next/dynamic";
import { forwardRef } from "react";
import type { ScenarioId } from "@/lib/api/types";
import { RISK_CLASSES, RISK_LABEL, RISK_META, type LossLevel } from "@/lib/design/colors";
import { fmtPct, fmtPctRange, fmtT, fmtUsd } from "@/lib/design/format";
import { Logo } from "@/components/atoms/Logo";
import { Icon } from "@/components/atoms/Icon";
import { Swatch } from "@/components/atoms/Swatch";
import { HatchDefs } from "@/components/atoms/HatchDefs";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";
import { today, useTemplateData } from "./useTemplateData";

const LossMap = dynamic(() => import("@/components/organisms/LossMap"), { ssr: false });

/**
 * Plantilla · tarjeta para compartir (1080 × 1080, redes y WhatsApp). Siempre en tema Misión.
 * Una cifra, un nivel de alerta, un mapa y una acción: legible en el teléfono.
 */
export const ShareCard = forwardRef<HTMLDivElement, { canton: string; scenario: ScenarioId; demo: boolean }>(function ShareCard({ canton, scenario, demo }, ref) {
  const { d, strategies, scenarioLabel, enso, geo, context, values } = useTemplateData(canton, scenario);
  const top = strategies?.items.find((s) => s.rank === 1);
  return (
    <div ref={ref} data-theme="mision" className="relative flex h-[1080px] w-[1080px] flex-col gap-8 overflow-hidden bg-surface-lowest p-[72px] font-sans text-on-surface">
      <HatchDefs />
      <div aria-hidden className="pointer-events-none absolute -top-40 -right-40 size-[620px] rounded-full bg-primary/10 blur-3xl" />
      <header className="flex items-center gap-4">
        <Logo size={56} />
        <div className="flex-1">
          <div className="font-display text-[32px] font-extrabold leading-9">CacaoResiliente</div>
          <div className="text-[16px] font-semibold uppercase tracking-[1.5px] text-on-surface-variant">Field Shift · NASA Space Apps 2026</div>
        </div>
        {enso?.phase === "nino" && (
          <span className="inline-flex items-center gap-2 rounded-full bg-neon-yellow px-5 py-2 font-display text-[20px] font-extrabold text-deep-blue">
            <Icon name="warning" fill size={24} /> El Niño {enso.strength?.replace("_", " ")}
          </span>
        )}
      </header>

      {d && d.loss ? (
        <div className="grid flex-1 grid-cols-[1fr_420px] gap-10">
          <div className="flex flex-col gap-5">
            <span className="text-[22px] font-semibold text-on-surface-variant">Pérdida estimada de cacao · {scenarioLabel}</span>
            <div>
              <div className="font-display text-[76px] font-black leading-[80px]">{d.area.name}</div>
              <div className="text-[26px] text-on-surface-variant">{d.area.province}</div>
            </div>
            <div className="whitespace-nowrap font-display text-[140px] font-black leading-[140px] tracking-tight tabular">{fmtPct(d.loss.loss_pct)}</div>
            <div className="origin-left scale-[1.6] self-start"><AlertLevelChip risk={d.loss.risk_class} prefix="Pérdida" detail /></div>
            <div className="mt-6 text-[22px] text-on-surface-variant">Rango probable {fmtPctRange(d.loss.loss_pct_low, d.loss.loss_pct_high)} · {fmtT(d.loss.loss_t)} · {fmtUsd(d.loss.loss_usd)}</div>
          </div>
          <div className="flex flex-col gap-4">
            <div className="relative h-[460px] overflow-hidden rounded-[28px] border border-outline-variant bg-surface">
              {geo && <LossMap className="absolute inset-0" areas={geo} context={context} mode="perdida" values={values} selectedId={canton}
                theme="mision" interactive={false} decorations={false} focus="selected" ariaLabel={`Mapa de ${d.area.name}`} />}
            </div>
            <ul className="grid grid-cols-5 gap-2">
              {RISK_CLASSES.map((c, i) => (
                <li key={c} className="flex flex-col items-start gap-1.5 text-[15px]">
                  <Swatch level={i as LossLevel} className="!h-4 !w-full" />{RISK_LABEL[c]}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : <div className="flex-1 animate-pulse rounded-[28px] bg-surface-high" />}

      {top && d && d.loss && (
        <div className="flex items-start gap-5 rounded-[28px] bg-primary-container p-7 text-on-primary-container">
          <Icon name="agriculture" fill size={44} />
          <div>
            <div className="text-[18px] font-bold uppercase tracking-[1px] opacity-80">Qué hacer primero · {RISK_META[d.loss.risk_class].alert}</div>
            <div className="font-display text-[34px] font-extrabold leading-10">{top.name}</div>
          </div>
        </div>
      )}
      <footer className="flex items-end justify-between gap-6 text-[15px] leading-5 text-on-surface-muted">
        <span>Datos: NASA POWER · ERA5-Land · NOAA CPC · ESPAC/INEC · {today()}<br />Estimación de un modelo: validar con INIAP o el MAG antes de invertir.</span>
        {demo && <span className="shrink-0 rounded-sm border-2 border-error px-3 py-1 font-display text-[18px] font-extrabold uppercase text-error">Datos de demostración</span>}
      </footer>
    </div>
  );
});
