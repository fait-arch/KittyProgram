"use client";
import { useState } from "react";
import Link from "next/link";
import { useAlerts, useScenarios } from "@/lib/api/hooks";
import type { AlertItem, ScenarioId } from "@/lib/api/types";
import { LOSS_RAMP, lossClassIndex, RISK_LABEL, RISK_META } from "@/lib/design/colors";
import { fmtPct, fmtPctRange, fmtT, fmtUsd } from "@/lib/design/format";
import type { Consulta } from "@/lib/whatsapp";
import { Icon } from "@/components/atoms/Icon";
import { Skeleton } from "@/components/atoms/Skeleton";
import { CacaoLoader, EmptyCacao } from "@/components/atoms/Anim";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";
import { LossInterval } from "@/components/molecules/LossInterval";
import { SegmentedButton } from "@/components/molecules/SegmentedButton";
import { WhatsAppButton } from "@/components/molecules/WhatsAppButton";

const OPTIONS: { value: ScenarioId; label: string }[] = [
  { value: "actual", label: "Temporada actual" },
  { value: "nino_extremo", label: "Niño extremo" },
  { value: "nino", label: "Año Niño" },
  { value: "normal", label: "Año normal" },
];

/**
 * Pantalla · Alertas en lenguaje natural (Fase 2).
 * Las cifras y el nivel salen del modelo; el texto lo redacta el LLM del backend (o una plantilla si no hay IA).
 */
export function AlertsScreen() {
  const [scenario, setScenario] = useState<ScenarioId>("actual");
  const { data, error, isLoading } = useAlerts(scenario);
  const { data: scenarios } = useScenarios();
  const scLabel = scenarios?.find((s) => s.id === scenario)?.label ?? OPTIONS.find((o) => o.value === scenario)?.label ?? scenario;

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-6 p-4 lg:p-8">
      <header className="flex flex-col gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Alertas · Fase 2</span>
        <h1 className="font-display text-[30px] font-extrabold leading-9">¿Qué está pasando y qué hacer?</h1>
        <SegmentedButton label="Escenario de las alertas" value={scenario} onChange={setScenario}
          options={OPTIONS.map((o) => ({ ...o, disabled: scenarios ? !scenarios.find((s) => s.id === o.value)?.available : false }))} />
      </header>

      {data ? (
        <section aria-label="Resumen" className="flex flex-col gap-3 rounded-xl bg-primary-container p-5 text-on-primary-container">
          <div className="flex items-start gap-3">
            <Icon name="campaign" fill size={28} />
            <p className="text-[17px] leading-[26px] font-medium">{data.resumen}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-surface-lowest/60 px-3 py-1 text-xs font-semibold text-on-surface">
            <Icon name={data.generated_by === "ia" ? "auto_awesome" : "edit_note"} size={16} />
            {data.generated_by === "ia"
              ? `Redactado con IA${data.provider ? ` (${data.provider === "anthropic" ? "Claude" : "DeepSeek"})` : ""} a partir de las cifras del modelo`
              : "Texto automático con las cifras del modelo (la IA no está configurada o no respondió)"}
          </span>
        </section>
      ) : error && !isLoading ? (
        <p className="rounded-lg bg-error-container p-4 text-on-error-container">No se pudieron cargar las alertas: {String(error.message ?? "")}. Revise que el backend esté encendido y vuelva a intentar.</p>
      ) : (
        <Skeleton className="h-28 rounded-xl" />
      )}

      <div className="stagger flex flex-col gap-4">
        {data?.items.map((a) => <AlertCard key={a.area_id} a={a} scLabel={scLabel} scenario={scenario} />)}
        {isLoading && !data && <div className="flex flex-col items-center gap-2 self-center py-10 text-center">
            <CacaoLoader label="La IA está redactando las alertas" />
            <span className="max-w-[46ch] text-sm text-on-surface-variant">La primera vez puede tardar hasta un minuto. Después se guardan y cargan al instante.</span>
          </div>}
        {data && !data.items.length && (
          <EmptyCacao className="rounded-xl bg-surface-high p-5" title="Sin alertas para este escenario">
            El modelo todavía no tiene estimaciones para este escenario.
          </EmptyCacao>
        )}
      </div>

      {data && (
        <p className="flex gap-2 text-xs leading-[18px] text-on-surface-variant">
          <Icon name="info" size={18} />
          {data.disclaimer} Las alertas son por provincia porque el modelo se entrena con la producción provincial (INEC-ESPAC).
        </p>
      )}
    </div>
  );
}

function AlertCard({ a, scLabel, scenario }: { a: AlertItem; scLabel: string; scenario: ScenarioId }) {
  const color = LOSS_RAMP[lossClassIndex(a.perdida_pct)];
  const consulta: Consulta = {
    tipo: "provincia", nombre: a.provincia, escenario: scLabel, perdidaPct: a.perdida_pct, rango: a.rango_pct, nivel: RISK_LABEL[a.nivel],
  };
  return (
    <article className="lift relative flex flex-col gap-4 overflow-hidden rounded-xl border border-outline-variant bg-surface-lowest p-5 pl-7 shadow-sm">
      <span aria-hidden className="absolute inset-y-0 left-0 w-2" style={{ background: color }} />
      <div className="flex flex-wrap items-start gap-3">
        <div className="mr-auto flex flex-col gap-1">
          <h2 className="font-display text-xl font-extrabold leading-7">{a.titulo}</h2>
          <span className="text-sm text-on-surface-variant">{RISK_META[a.nivel].alert} · {scLabel}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-display text-[34px] font-black leading-10 tabular">{fmtPct(a.perdida_pct)}</span>
          <AlertLevelChip risk={a.nivel} prefix="Pérdida" />
        </div>
      </div>

      <p className="text-[16px] leading-[25px]">{a.mensaje}</p>

      <div className="flex gap-3 rounded-lg bg-surface-container p-4">
        <Icon name="agriculture" fill size={24} className="text-primary" />
        <div className="flex flex-col gap-1">
          <b className="text-sm">Qué hacer</b>
          <span className="text-[15px] leading-[22px]">{a.accion}</span>
          <span className="flex items-center gap-1 text-[13px] text-on-surface-variant"><Icon name="schedule" size={16} />{a.cuando}</span>
        </div>
      </div>

      <details className="group rounded-lg border border-outline-variant px-4 py-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-on-surface-variant [&::-webkit-details-marker]:hidden">
          <Icon name="expand_more" size={18} className="transition-transform duration-300 group-open:rotate-180" />
          Ver el cálculo{a.cantones.length ? ` y los ${a.cantones.length} cantones` : ""}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <LossInterval low={a.rango_pct[0] ?? a.perdida_pct} mid={a.perdida_pct} high={a.rango_pct[1] ?? a.perdida_pct} />
          <span className="text-[13px] text-on-surface-variant">
            Rango probable {fmtPctRange(a.rango_pct[0] ?? a.perdida_pct, a.rango_pct[1] ?? a.perdida_pct)}
            {a.perdida_t != null && <> · {fmtT(a.perdida_t)} · {fmtUsd(a.perdida_usd)}</>}
            {a.factor_principal && <> · Lo que más pesa: {a.factor_principal.toLowerCase()}</>}
          </span>
          <div className="flex flex-wrap gap-2 text-xs">
            {a.evidencia === "indice_subnacional_no_validado" && <Tag icon="travel_explore">Estimación por zona</Tag>}
            {a.extrapolado && <Tag icon="warning">Más extremo que lo observado</Tag>}
            {a.prob_perder_mas_20 != null && <Tag icon="casino">{Math.round(a.prob_perder_mas_20 * 100)} % de probabilidad de perder más del 20 %</Tag>}
          </div>
          {!!a.cantones.length && (
            <div className="flex flex-wrap gap-1.5">
              {a.cantones.map((c) => <span key={c} className="rounded-sm bg-surface-high px-2 py-0.5 text-xs">{c}</span>)}
            </div>
          )}
          <Link href={`/?escenario=${scenario}`} className="text-sm font-bold text-link">Abrir el mapa →</Link>
        </div>
      </details>

      <WhatsAppButton consulta={consulta} label={`Consultar a un asesor sobre ${a.provincia}`} />
    </article>
  );
}

function Tag({ icon, children }: { icon: string; children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1 rounded-full bg-surface-container px-2.5 py-1 font-semibold"><Icon name={icon} size={14} />{children}</span>;
}
