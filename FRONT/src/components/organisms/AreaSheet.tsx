"use client";
import { useEffect, useState } from "react";
import { RISK_LABEL } from "@/lib/design/colors";
import { rememberConsulta, type Consulta } from "@/lib/whatsapp";
import { WhatsAppButton } from "@/components/molecules/WhatsAppButton";
import { fmtMae, fmtYears } from "@/lib/design/format";
import Link from "next/link";
import { useAreaDetail, useAreas, useAreaStrategies, useProvinceLosses, useRequirements, useScenarios } from "@/lib/api/hooks";
import type { ScenarioId } from "@/lib/api/types";
import { fmtInt } from "@/lib/design/format";
import { cn } from "@/lib/cn";
import { IconButton, LinkButton } from "@/components/atoms/Button";
import { SaveOfflineButton } from "@/components/molecules/SaveOfflineButton";
import { Icon } from "@/components/atoms/Icon";
import { CacaoLoader } from "@/components/atoms/Anim";
import { LossHero } from "@/components/organisms/LossHero";
import { FactorBars } from "@/components/organisms/FactorBars";
import { MonthlyRiskChart } from "@/components/organisms/MonthlyRiskChart";
import { RequirementCheck } from "@/components/organisms/RequirementCheck";
import { StrategyCards } from "@/components/organisms/StrategyCards";

/**
 * Panel del cantón. Escritorio: hoja lateral (side sheet) para que el mapa siga visible.
 * Móvil: hoja inferior expandible.
 */
export function AreaSheet({ id, scenario, onClose }: { id: string; scenario: ScenarioId; onClose: () => void }) {
  const detail = useAreaDetail(id, scenario);
  const strategies = useAreaStrategies(id, scenario);
  const req = useRequirements();
  const { data: scenarios } = useScenarios();
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const d = detail.data;
  const scLabel = scenarios?.find((s) => s.id === scenario)?.label ?? scenario;
  const { data: provLosses } = useProvinceLosses(scenario);
  const { data: provAreas } = useAreas("province");

  // Consulta concreta: el botón de WhatsApp (aquí y en la barra superior) la lleva al chat
  const consulta: Consulta | null = d ? {
    tipo: "canton", nombre: d.area.name, provincia: d.area.province, escenario: scLabel,
    perdidaPct: d.loss?.loss_pct ?? null, rango: d.loss ? [d.loss.loss_pct_low, d.loss.loss_pct_high] : undefined,
    nivel: d.loss ? RISK_LABEL[d.loss.risk_class] : null,
    url: typeof window !== "undefined" ? window.location.href : undefined,
  } : null;
  const consultaKey = consulta ? `${consulta.nombre}|${consulta.escenario}|${consulta.perdidaPct}` : "";
  useEffect(() => {
    if (consulta) rememberConsulta(consulta);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consultaKey]);

  return (
    <aside
      aria-label={d ? `Detalle del cantón ${d.area.name}` : "Detalle del cantón"}
      className={cn(
        "z-[1000] flex flex-col overflow-y-auto bg-surface-low shadow-[0_-4px_16px_rgb(0_0_0/0.3)]",
        "fixed inset-x-0 bottom-20 rounded-t-xl",
        expanded ? "top-24" : "max-h-[46dvh]",
        "lg:static lg:inset-auto lg:max-h-none lg:w-[540px] lg:shrink-0 lg:rounded-none lg:rounded-l-lg lg:border-l lg:border-outline-variant lg:shadow-none",
      )}
    >
      <button type="button" onClick={() => setExpanded((e) => !e)} aria-label={expanded ? "Contraer panel" : "Expandir panel"}
        className="mx-auto mt-2 mb-1 h-6 w-16 shrink-0 cursor-pointer lg:hidden">
        <span className="mx-auto block h-1 w-8 rounded-full bg-outline" />
      </button>
      <div className="flex flex-col gap-7 px-5 pb-8 lg:px-7 lg:pt-6">
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-outline px-3 text-[13px] font-semibold text-on-surface-variant">
              <Icon name="thunderstorm" size={18} />
              {scLabel}
            </span>
            <span className="flex-1" />
            <IconButton icon={copied ? "check" : "share"} label={copied ? "Enlace copiado" : "Copiar enlace"} onClick={() => {
              navigator.clipboard?.writeText(window.location.href).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800); }).catch(() => {});
            }} />
            <IconButton icon="close" label="Cerrar panel" onClick={onClose} />
          </div>
          {d ? (
            <>
              <h1 className="font-display text-[40px] leading-[48px] font-black">{d.area.name}</h1>
              <p className="text-[15px] text-on-surface-variant">
                {d.area.province}
                {d.area.cacao_ha != null && <> · {fmtInt(d.area.cacao_ha)} ha de cacao</>}
              </p>
              <div className="mt-1 flex flex-wrap gap-2">
                <LinkButton variant="filled" icon="compare_arrows" href={`/comparar?canton=${encodeURIComponent(id)}`}>Comparar escenarios</LinkButton>
                <details className="group relative">
                  <summary className="state-layer inline-flex h-10 cursor-pointer list-none items-center gap-1.5 rounded-full border border-outline px-4 text-sm font-bold [&::-webkit-details-marker]:hidden">
                    <Icon name="ios_share" size={18} />Compartir<Icon name="expand_more" size={18} className="transition-transform group-open:rotate-180" />
                  </summary>
                  <div className="absolute left-0 z-20 mt-2 flex w-64 flex-col gap-1 rounded-lg border border-outline-variant bg-surface-lowest p-2 shadow-xl">
                    <Link href={`/plantillas?tipo=tarjeta&canton=${encodeURIComponent(id)}&escenario=${scenario}`} className="state-layer flex items-center gap-2 rounded-md px-3 py-2 text-sm"><Icon name="image" size={20} className="text-primary" />Tarjeta para redes</Link>
                    <Link href={`/plantillas?tipo=ficha&canton=${encodeURIComponent(id)}&escenario=${scenario}`} className="state-layer flex items-center gap-2 rounded-md px-3 py-2 text-sm"><Icon name="print" size={20} className="text-primary" />Ficha A4 para el técnico</Link>
                    <div className="border-t border-outline-variant pt-2"><SaveOfflineButton id={id} name={d.area.name} /></div>
                  </div>
                </details>
              </div>
            </>
          ) : detail.error ? (
            <p className="text-error">No se pudo cargar el cantón. {String(detail.error.message ?? "")}</p>
          ) : (
            <CacaoLoader label="Cargando el cantón" className="self-start py-6" />
          )}
        </div>

        {d && <LossHero d={d} scenarioLabel={scLabel} province={provinceTotals(d.area.province, provAreas, provLosses?.items)} />}
        {d && (
          <div className="-mt-3 flex flex-col gap-1.5">
            <WhatsAppButton consulta={consulta} />
            <span className="text-xs text-on-surface-variant">Abre WhatsApp con su consulta de {d.area.name} ya escrita.</span>
          </div>
        )}
        {d && <FactorBars factors={d.top_factors} />}
        {d && <MonthlyRiskChart data={d.monthly_risk} />}
        {d && req.data && <RequirementCheck climate={d.climate} req={req.data} />}
        {strategies.data ? <StrategyCards data={strategies.data} /> : d && !strategies.error && d.loss && <div className="h-40 animate-pulse rounded-lg bg-surface-high" />}

        {d && (
          <section aria-label="Aviso" className="flex gap-3 rounded-md bg-surface-high p-4">
            <Icon name="info" className="text-primary" />
            <div className="flex flex-col gap-1.5 text-[13px] leading-[19px]">
              <span><b>{d.disclaimer}</b> Apoya, no reemplaza, al técnico.</span>
              {!!d.data_gaps?.length && (
                <ul className="list-disc pl-4 text-on-surface-variant">
                  {d.data_gaps.map((g) => <li key={g}>{g}</li>)}
                </ul>
              )}
              <span className="text-on-surface-variant">
                Modelo {d.model.name} · MAE {fmtMae(d.model.mae)} · entrenado {fmtYears(d.model.trained_years)}
              </span>
              <Link href="/metodologia" className="font-bold text-link">Ver metodología y fuentes</Link>
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}

/** Totales de la provincia del cantón (t y USD) para el escenario elegido. */
function provinceTotals(name: string | undefined, areas: { id: string; name: string }[] | undefined, items: { area_id: string; loss_t: number | null; loss_usd: number | null }[] | undefined) {
  if (!name || !areas || !items) return null;
  const norm = (x: string) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  const prov = areas.find((a) => norm(a.name) === norm(name));
  const it = prov && items.find((i) => i.area_id === prov.id);
  return it ? { name: prov!.name, loss_t: it.loss_t, loss_usd: it.loss_usd } : null;
}
