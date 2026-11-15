"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useAlerts, useAreas, useEnso, useLosses, useLossSummary, useScenarios, useZones } from "@/lib/api/hooks";
import { LOSS_RAMP, lossClassIndex } from "@/lib/design/colors";
import type { ScenarioId } from "@/lib/api/types";
import { useMapState } from "@/lib/state/useMapState";
import { fmt2, fmtDeltaT, fmtDeltaUsd, fmtInt, fmtPct, fmtT, fmtUsd } from "@/lib/design/format";
import { Icon } from "@/components/atoms/Icon";
import { Skeleton } from "@/components/atoms/Skeleton";
import { CountUp } from "@/components/molecules/CountUp";
import { ScenarioSelector } from "@/components/molecules/ScenarioSelector";
import { PanelCard, StatCard } from "@/components/molecules/StatCard";
import { ClassMixChart } from "@/components/organisms/ClassMixChart";

/**
 * Pantalla · Panel general (estructura de la plantilla Harvest: indicadores, tres tarjetas, gráfico grande con
 * recomendaciones al lado). Sin repetir lo que ya está en el menú: poco ruido, una idea por tarjeta.
 */
export function PanelScreen() {
  const st = useMapState();
  const scenario = st.scenario;
  const { data: scenarios } = useScenarios();
  const { data: sum, isLoading } = useLossSummary(scenario);
  const { data: losses } = useLosses(scenario);
  const { data: normal } = useLosses("normal");
  const { data: enso } = useEnso();
  const { data: zones } = useZones("ssp245_2050");
  const { data: areas } = useAreas("canton");
  const { data: alerts } = useAlerts("actual");
  const topAlert = alerts?.items[0];
  const scLabel = scenarios?.find((s) => s.id === scenario)?.label ?? scenario;
  const byId = useMemo(() => new Map((areas ?? []).map((a) => [a.id, a])), [areas]);

  const red = sum ? sum.areas_by_class.muy_alta + sum.areas_by_class.critica : 0;
  const normalPct = useMemo(() => new Map((normal?.items ?? []).map((i) => [i.area_id, i.loss_pct])), [normal]);
  const rising = useMemo(() => (losses?.items ?? [])
    .map((i) => ({ ...i, delta: i.loss_pct - (normalPct.get(i.area_id) ?? i.loss_pct) }))
    .sort((a, b) => b.loss_pct - a.loss_pct).slice(0, 6), [losses, normalPct]);
  const haTotal = (areas ?? []).reduce((s, a) => s + (a.cacao_ha ?? 0), 0);
  const apt = (zones?.items ?? []).filter((z) => z.suitability_score >= 0.7);
  const safe = apt.filter((z) => z.zone === "segura").length;
  const redByProv = useMemo(() => {
    const c = new Map<string, number>();
    for (const i of losses?.items ?? []) if (i.risk_class === "muy_alta" || i.risk_class === "critica") {
      const p = byId.get(i.area_id)?.province ?? "?";
      c.set(p, (c.get(p) ?? 0) + 1);
    }
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [losses, byId]);

  const recs = [
    enso?.phase === "nino" && { icon: "thunderstorm", tone: "warn", title: "Adelante el manejo sanitario", text: "El Niño está en curso: podas, remoción semanal de mazorcas enfermas y drenaje antes del pico de lluvias (enero a marzo)." },
    redByProv[0] && { icon: "priority_high", tone: "bad", title: `Priorice ${redByProv[0][0]}`, text: `${redByProv[0][1]} cantones en alerta roja (pérdida > 30 %) en ${scLabel}. Ahí la asistencia técnica rinde más.` },
    safe > 0 && { icon: "eco", tone: "good", title: "Dónde ampliar siembras", text: `${safe} cantones tienen aptitud alta y riesgo bajo hacia 2050 (zona segura). Véalos con las mazorcas del mapa satelital.` },
    { icon: "water_drop", tone: "info", title: "Drenaje y sombra regulada", text: "En suelos que se encharcan, drenar y regular la sombra baja la humedad que favorece a la moniliasis." },
  ].filter(Boolean).slice(0, 3) as { icon: string; tone: string; title: string; text: string }[];


  return (
    <div className="mx-auto flex max-w-[1400px] flex-col gap-6 p-4 lg:p-8">
      <header className="flex flex-wrap items-end gap-4">
        <div className="mr-auto">
          <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Panel general · Costa y Amazonía del Ecuador</span>
          <h1 className="font-display text-[30px] font-extrabold leading-9">¿Cómo va el cacao esta temporada?</h1>
        </div>
        <ScenarioSelector compact value={scenario} onChange={st.setScenario} scenarios={scenarios} />
      </header>

      {/* Indicadores */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon="grass" loading={isLoading} value={<CountUp value={sum?.loss_t} format={fmtT} />} label={`Cacao perdido · ${scLabel}`}
          foot={sum?.vs_normal ? `${fmtDeltaT(sum.vs_normal.loss_t)} frente a un año normal` : "Año de referencia"} />
        <StatCard icon="payments" loading={isLoading} value={<CountUp value={sum?.loss_usd} format={fmtUsd} />} label="Valor en riesgo"
          foot={sum?.vs_normal ? `${fmtDeltaUsd(sum.vs_normal.loss_usd)} frente a un año normal` : undefined} />
        <StatCard icon="notifications_active" loading={isLoading} value={sum ? `${red} de ${sum.n_areas}` : "—"} label="Cantones en alerta roja"
          foot="Pérdida mayor a 30 % (IPC 4–5 · SNGR roja)" />
        <StatCard icon="waves" loading={!enso} value={enso ? `${enso.oni.value >= 0 ? "+" : ""}${fmt2(enso.oni.value)}` : "—"} label="Índice ONI · El Niño"
          foot={enso ? `Niño 1+2: ${enso.nino12.anomaly_c >= 0 ? "+" : ""}${fmt2(enso.nino12.anomaly_c)} °C · ${enso.source}` : undefined} />
      </div>

      {/* Alerta principal (lenguaje natural) */}
      {topAlert && (
        <Link href="/alertas" className="lift state-layer relative flex flex-wrap items-center gap-4 overflow-hidden rounded-xl border border-outline-variant bg-surface-lowest p-5 pl-7 shadow-sm">
          <span aria-hidden className="absolute inset-y-0 left-0 w-2" style={{ background: LOSS_RAMP[lossClassIndex(topAlert.perdida_pct)] }} />
          <Icon name="campaign" fill size={30} className="text-primary" />
          <span className="flex min-w-[240px] flex-1 flex-col gap-0.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Alerta principal · temporada actual</span>
            <b className="font-display text-lg leading-6">{topAlert.titulo}</b>
            <span className="text-sm text-on-surface-variant">{topAlert.mensaje}</span>
          </span>
          <span className="text-sm font-bold text-link">Ver {alerts.items.length} alertas →</span>
        </Link>
      )}

      {/* Tres tarjetas */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PanelCard title="El Niño hoy" icon="thunderstorm">
          {enso ? (
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-on-surface-variant">Mar frente a Ecuador (Niño 1+2)</p>
                <p className="font-display text-[40px] font-black leading-[44px] tabular">{enso.nino12.anomaly_c >= 0 ? "+" : ""}{fmt2(enso.nino12.anomaly_c)} °C</p>
                <p className="mt-1 text-sm">{enso.phase === "nino" ? "Más lluvia y humedad en la Costa: más moniliasis y mazorca negra." : "Condiciones cercanas a lo normal."}</p>
              </div>
              <Icon name={enso.phase === "nino" ? "rainy" : "partly_cloudy_day"} size={56} className="text-series-monilia" />
            </div>
          ) : <Skeleton className="h-28" />}
          <Link href="/metodologia#enso" className="text-sm font-bold text-link">¿Qué significa para mi cacao? →</Link>
        </PanelCard>

        <PanelCard title="Cacao en Costa y Amazonía" icon="eco">
          <div className="grid grid-cols-2 gap-3">
            <div><p className="font-display text-2xl font-extrabold tabular">{haTotal ? fmtInt(haTotal) : "—"}</p><p className="text-xs text-on-surface-variant">hectáreas de cacao</p></div>
            <div><p className="font-display text-2xl font-extrabold tabular">{apt.length || "—"}</p><p className="text-xs text-on-surface-variant">cantones con aptitud alta</p></div>
          </div>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-high" role="img" aria-label={`${safe} de ${apt.length} cantones aptos están en zona segura hacia 2050`}>
            <div className="bg-zone-segura" style={{ width: apt.length ? `${(safe / apt.length) * 100}%` : 0 }} />
            <div className="bg-zone-manejo" style={{ width: apt.length ? `${((apt.length - safe) / apt.length) * 100}%` : 0 }} />
          </div>
          <p className="text-xs text-on-surface-variant"><b className="text-on-surface">{safe}</b> en zona segura y <b className="text-on-surface">{apt.length - safe}</b> en zona de manejo hacia 2050 (SSP2-4.5).</p>
        </PanelCard>

        <PanelCard title="Más afectados" icon="priority_high" action={<Link href={`/?escenario=${scenario}&tabla=1`} className="text-sm font-bold text-link">Ver todos</Link>}>
          <ul className="flex flex-col gap-2.5">
            {rising.slice(0, 5).map((i, k) => (
              <li key={i.area_id}>
                <Link href={`/?escenario=${scenario}&canton=${encodeURIComponent(i.area_id)}`} className="state-layer -mx-2 flex items-center gap-3 rounded-md px-2 py-1">
                  <span className="w-4 text-sm font-bold text-on-surface-muted tabular">{k + 1}</span>
                  <span className="flex-1"><b className="block text-sm">{byId.get(i.area_id)?.name ?? i.area_id}</b><span className="text-xs text-on-surface-variant">{byId.get(i.area_id)?.province}</span></span>
                  <span className="font-display font-extrabold tabular">{fmtPct(i.loss_pct)}</span>
                </Link>
              </li>
            ))}
            {!losses && <Skeleton className="h-40" />}
          </ul>
        </PanelCard>
      </div>

      {/* Gráfico + recomendaciones */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-outline-variant bg-surface-lowest p-5 shadow-sm lg:col-span-2">
          <ClassMixChart scenarios={scenarios} />
        </div>
        <PanelCard title="Recomendaciones" icon="tips_and_updates">
          <ul className="flex flex-col gap-3">
            {recs.map((r) => (
              <li key={r.title} className="flex gap-3 rounded-lg bg-surface-container p-3">
                <Icon name={r.icon} fill size={22} className={r.tone === "bad" ? "text-error" : r.tone === "warn" ? "text-status-warn" : "text-primary"} />
                <span><b className="block text-sm">{r.title}</b><span className="text-[13px] leading-[18px] text-on-surface-variant">{r.text}</span></span>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-on-surface-muted">Reglas a partir de los datos del modelo. Validar con INIAP o el MAG.</p>
        </PanelCard>
      </div>

    </div>
  );
}
