"use client";
import dynamic from "next/dynamic";
import { forwardRef } from "react";
import type { ScenarioId } from "@/lib/api/types";
import { RISK_CLASSES, RISK_LABEL, RISK_RANGE, type LossLevel } from "@/lib/design/colors";
import { fmt2 } from "@/lib/design/format";
import { Logo } from "@/components/atoms/Logo";
import { Icon } from "@/components/atoms/Icon";
import { Swatch } from "@/components/atoms/Swatch";
import { HatchDefs } from "@/components/atoms/HatchDefs";
import { useTemplateData } from "./useTemplateData";

const LossMap = dynamic(() => import("@/components/organisms/LossMap"), { ssr: false });

/** Plantilla · portada del video y de la presentación (1920 × 1080, 16:9). Tema Misión, mapa de toda la Costa. */
export const VideoCover = forwardRef<HTMLDivElement, { canton: string; scenario: ScenarioId; demo: boolean }>(function VideoCover({ canton, scenario, demo }, ref) {
  const { scenarioLabel, enso, geo, context, values } = useTemplateData(canton, scenario);
  return (
    <div ref={ref} data-theme="mision" className="relative grid h-[1080px] w-[1920px] grid-cols-[1fr_820px] overflow-hidden bg-surface-lowest font-sans text-on-surface">
      <HatchDefs />
      <div aria-hidden className="absolute inset-0 bg-linear-to-br from-primary-container/60 via-transparent to-transparent" />
      <div aria-hidden className="absolute -bottom-60 -left-40 size-[900px] rounded-full bg-primary/10 blur-3xl" />
      <div className="relative flex flex-col justify-between p-[120px] pr-10">
        <div className="flex items-center gap-5">
          <Logo size={72} />
          <div>
            <div className="font-display text-[44px] font-extrabold leading-[48px]">CacaoResiliente</div>
            <div className="text-[20px] font-semibold uppercase tracking-[2px] text-on-surface-variant">Field Shift · NASA Space Apps Challenge 2026</div>
          </div>
        </div>
        <div className="flex flex-col gap-8">
          <h1 className="font-display text-[104px] font-black leading-[108px]">
            ¿Cuánto cacao se pierde cuando llega <span className="text-primary">El Niño</span>?
          </h1>
          <p className="max-w-[860px] text-[30px] leading-10 text-on-surface-variant">
            Pérdida estimada por moniliasis y mazorca negra en cada cantón de la Costa del Ecuador, con datos de la NASA, hoy y en 2050.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {enso?.phase === "nino" && (
            <span className="inline-flex items-center gap-3 rounded-full bg-neon-yellow px-6 py-2.5 font-display text-[24px] font-extrabold text-deep-blue">
              <Icon name="warning" fill size={30} /> El Niño en curso · ONI +{fmt2(enso.oni.value)}
            </span>
          )}
          <span className="rounded-full border-2 border-outline px-6 py-2.5 text-[24px] font-semibold">Mapa: {scenarioLabel}</span>
          {demo && <span className="rounded-full border-2 border-error px-6 py-2.5 text-[22px] font-bold uppercase text-error">Datos de demostración</span>}
        </div>
      </div>
      <div className="relative">
        {geo && <LossMap className="absolute inset-0" areas={geo} context={context} mode="perdida" values={values} theme="mision"
          interactive={false} decorations={false} focus="all" selectedId={null} ariaLabel="Mapa de pérdida de la Costa" />}
        <ul className="absolute right-[64px] bottom-[64px] flex flex-col gap-3 rounded-[24px] border border-outline-variant bg-surface-low/90 p-7 text-[22px]">
          <li className="font-display text-[24px] font-bold">Pérdida estimada</li>
          {RISK_CLASSES.map((c, i) => (
            <li key={c} className="flex items-center gap-3"><Swatch level={i as LossLevel} className="!h-6 !w-9" /><span className="tabular">{RISK_RANGE[i]} %</span><span className="text-on-surface-variant">· {RISK_LABEL[c]}</span></li>
          ))}
        </ul>
      </div>
    </div>
  );
});
