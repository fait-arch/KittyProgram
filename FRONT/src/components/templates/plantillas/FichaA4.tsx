"use client";
import dynamic from "next/dynamic";
import { fmtMae, fmtYears } from "@/lib/design/format";
import { forwardRef } from "react";
import type { ScenarioId } from "@/lib/api/types";
import { fmtInt } from "@/lib/design/format";
import { Logo } from "@/components/atoms/Logo";
import { Icon } from "@/components/atoms/Icon";
import { HatchDefs } from "@/components/atoms/HatchDefs";
import { LossHero } from "@/components/organisms/LossHero";
import { FactorBars } from "@/components/organisms/FactorBars";
import { MonthlyRiskChart } from "@/components/organisms/MonthlyRiskChart";
import { StrategyCards } from "@/components/organisms/StrategyCards";
import { today, useTemplateData } from "./useTemplateData";

const LossMap = dynamic(() => import("@/components/organisms/LossMap"), { ssr: false });

/**
 * Plantilla · ficha imprimible A4 para el técnico (tema Campo: tinta oscura sobre papel).
 * Reutiliza los organismos del panel del cantón; se imprime o se guarda como PDF desde el navegador.
 */
export const FichaA4 = forwardRef<HTMLDivElement, { canton: string; scenario: ScenarioId; demo: boolean }>(function FichaA4({ canton, scenario, demo }, ref) {
  const { d, strategies, scenarioLabel, geo, context, values } = useTemplateData(canton, scenario);
  return (
    <div ref={ref} data-theme="campo" className="flex min-h-[1123px] w-[794px] flex-col bg-surface-lowest font-sans text-on-surface">
      <HatchDefs />
      <header className="flex items-center gap-3 bg-appbar px-10 py-4 text-on-appbar">
        <Logo size={32} />
        <div className="flex-1">
          <div className="font-display text-lg font-extrabold leading-5">CacaoResiliente · Ficha técnica del cantón</div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.8px] text-on-appbar-variant">Field Shift · NASA Space Apps 2026</div>
        </div>
        <span className="text-xs text-on-appbar-variant">{today()}</span>
      </header>
      {d ? (
        <div className="flex flex-1 flex-col gap-5 px-10 py-7">
          <div className="flex items-end gap-6">
            <div className="flex-1">
              <span className="text-xs font-semibold uppercase tracking-[0.8px] text-on-surface-variant">{scenarioLabel}</span>
              <h1 className="font-display text-[40px] font-black leading-[44px]">{d.area.name}</h1>
              <p className="text-sm text-on-surface-variant">{d.area.province}{d.area.cacao_ha != null && <> · {fmtInt(d.area.cacao_ha)} ha de cacao</>}</p>
            </div>
            <div className="relative h-[120px] w-[180px] overflow-hidden rounded-md border border-outline-variant">
              {geo && <LossMap className="absolute inset-0" areas={geo} context={context} mode="perdida" values={values} selectedId={canton}
                theme="campo" interactive={false} decorations={false} focus="selected" ariaLabel={`Ubicación de ${d.area.name}`} />}
            </div>
          </div>
          <LossHero d={d} scenarioLabel={scenarioLabel} />
          <div className="grid grid-cols-2 gap-6 [&_button]:hidden">
            <FactorBars factors={d.top_factors} />
            <MonthlyRiskChart data={d.monthly_risk} />
          </div>
          <div className="break-inside-avoid">{strategies && <StrategyCards data={strategies} />}</div>
          <div className="mt-auto flex gap-3 rounded-md border border-outline-variant p-4 text-[13px] leading-5">
            <Icon name="info" className="text-primary" />
            <p><b>Apoya, no reemplaza, al técnico.</b> {d.disclaimer} Modelo {d.model.name}, error medio {fmtMae(d.model.mae)}, entrenado {fmtYears(d.model.trained_years)}.
              {demo && <b className="text-error"> Datos de demostración: no usar para decisiones.</b>}</p>
          </div>
        </div>
      ) : <div className="m-10 h-[600px] animate-pulse rounded-lg bg-surface-high" />}
      <footer className="border-t border-outline-variant px-10 py-3 text-[11px] text-on-surface-muted">
        Fuentes: NASA POWER · ERA5-Land · NOAA CPC · ESPAC/INEC · ECOCROP (FAO). Escala de alerta: fases IPC y alertas SNGR.
      </footer>
    </div>
  );
});
