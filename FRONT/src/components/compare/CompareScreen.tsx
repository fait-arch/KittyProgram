"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import useSWR from "swr";
import type { FeatureCollection } from "geojson";
import { useAreas, useAreasGeojson, useCompare, useLosses, useScenarios, useZones } from "@/lib/api/hooks";
import type { LossesResponse, ScenarioId, Zone } from "@/lib/api/types";
import { fmt2, fmtPct, fmtPctRange, fmtT, fmtUsd } from "@/lib/design/format";
import { useMapState } from "@/lib/state/useMapState";
import { useTheme } from "@/lib/theme";
import { SegmentedButton } from "@/components/ui/SegmentedButton";
import { Icon } from "@/components/ui/Icon";
import { LossRangeChart } from "./LossRangeChart";
import { ZoneMatrix } from "./ZoneMatrix";

const LossMap = dynamic(() => import("@/components/map/LossMap"), { ssr: false });
const SCEN: ScenarioId[] = ["normal", "nino", "ssp245_2050", "ssp585_2050"];
const DEFAULT_ID = "los-rios-vinces";

/** Fase 2: el mismo cantón en cuatro climas + matriz de zonas 2050. */
export function CompareScreen() {
  const st = useMapState();
  const { theme } = useTheme();
  const { data: areas } = useAreas("canton");
  const { data: scenarios } = useScenarios();
  const { data: geo } = useAreasGeojson("canton");
  const { data: context } = useSWR("geo/contexto", () => fetch("/geo/ecuador-contexto.geojson").then((r) => r.json() as Promise<FeatureCollection>), { revalidateOnFocus: false });
  const id = st.canton ?? (areas?.some((a) => a.id === DEFAULT_ID) ? DEFAULT_ID : areas?.[0]?.id ?? null);
  const { data: cmp } = useCompare(id, SCEN);
  const l0 = useLosses("normal"), l1 = useLosses("nino"), l2 = useLosses("ssp245_2050"), l3 = useLosses("ssp585_2050");
  const lossBy: Record<string, LossesResponse | undefined> = { normal: l0.data, nino: l1.data, ssp245_2050: l2.data, ssp585_2050: l3.data };
  const [future, setFuture] = useState<ScenarioId>("ssp245_2050");
  const { data: zones } = useZones(future);
  const zoneMap = useMemo(() => new Map<string, Zone>(zones?.items.map((z) => [z.area_id, z.zone]) ?? []), [zones]);
  const label = (s: ScenarioId) => scenarios?.find((x) => x.id === s)?.label ?? s;

  return (
    <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex min-w-[280px] flex-1 flex-col gap-1.5">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
            Comparar escenarios
            <span className="rounded-full bg-neon-yellow px-1.5 font-display text-[10px] font-extrabold leading-4 tracking-normal text-deep-blue">FASE 2</span>
          </span>
          <h1 className="font-display text-[32px] leading-10 font-extrabold">El mismo cantón en cuatro climas</h1>
          <p className="text-[15px] text-on-surface-variant">Pérdida estimada hoy (año normal y año Niño) y con el clima de 2041–2060 (NEX-GDDP-CMIP6, método delta).</p>
        </div>
        <label className="flex h-14 min-w-[260px] flex-col justify-center rounded-sm border border-outline px-4">
          <span className="text-xs text-on-surface-variant">Cantón</span>
          <select value={id ?? ""} onChange={(e) => st.selectCanton(e.target.value)} className="bg-transparent text-base font-semibold outline-none">
            {areas?.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.province}</option>)}
          </select>
        </label>
      </div>

      <section aria-label="Comparación lado a lado" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {SCEN.map((s) => {
          const it = cmp?.items.find((i) => i.scenario === s);
          const values = new Map(lossBy[s]?.items.map((i) => [i.area_id, i.loss_pct]) ?? []);
          return (
            <article key={s} className={`flex flex-col overflow-hidden rounded-lg border bg-surface-low ${s === "nino" ? "border-primary" : "border-outline-variant"}`}>
              <div className="px-4 pt-3.5">
                <h2 className="font-display text-base font-bold">{label(s)}</h2>
                <p className="text-xs text-on-surface-variant">{s.endsWith("2050") ? "Clima 2041–2060" : "Hoy"}</p>
              </div>
              <LossMap className="relative mt-2.5 h-[200px]" interactive={false} decorations={false} focus="selected" areas={geo} context={context}
                mode="perdida" values={values} selectedId={id} theme={theme} ariaLabel={`Mapa de pérdida, ${label(s)}`} />
              <div className="flex flex-col gap-2 p-4">
                {it ? (
                  <>
                    <span className="font-display text-[40px] leading-[48px] font-black tabular">{fmtPct(it.loss.loss_pct)}</span>
                    <span className="text-[13px] text-on-surface-variant">Rango {fmtPctRange(it.loss.loss_pct_low, it.loss.loss_pct_high)}</span>
                    <span className="text-sm tabular">{fmtT(it.loss.loss_t)} · {fmtUsd(it.loss.loss_usd)}</span>
                    <span className="inline-flex h-7 items-center gap-1.5 self-start rounded-sm bg-surface-high px-2.5 text-xs font-semibold">
                      <span style={{ color: it.suitability.class === "apta" ? "var(--color-status-ok)" : it.suitability.class === "marginal" ? "var(--color-status-marginal)" : "var(--color-status-out)" }}>
                        <Icon name={it.suitability.class === "apta" ? "check_circle" : it.suitability.class === "marginal" ? "error" : "dangerous"} fill size={16} />
                      </span>
                      Aptitud {fmt2(it.suitability.score)} · {it.suitability.class.replace("_", " ")}
                    </span>
                    {it.extrapolation && <span className="text-xs text-on-surface-muted">Extrapolación: leer como tendencia.</span>}
                  </>
                ) : (
                  <div className="h-28 animate-pulse rounded-md bg-surface-high" />
                )}
              </div>
            </article>
          );
        })}
      </section>

      {cmp && (
        <section aria-label="Cómo cambia la pérdida" className="flex flex-wrap gap-6 rounded-lg border border-outline-variant bg-surface p-6">
          <div className="flex min-w-[300px] flex-[2] flex-col gap-3">
            <div>
              <h2 className="font-display text-xl font-bold">Cómo cambia la pérdida en {cmp.area.name}</h2>
              <p className="text-[13px] text-on-surface-variant">Estimación central y rango probable (p10–p90), % de la producción</p>
            </div>
            <LossRangeChart items={cmp.items} scenarios={scenarios} />
          </div>
          <div className="flex min-w-[240px] flex-1 flex-col gap-3 text-sm leading-[21px]">
            <span className="text-xs font-bold uppercase tracking-wide text-on-surface-variant">Lectura</span>
            <p className="flex gap-2 rounded-md bg-surface-container p-3 text-[13px] leading-[18px]">
              <Icon name="warning" fill size={18} className="text-status-warn" />
              2050 es extrapolación: el modelo se aplica fuera del clima con que se entrenó. El rango incluye la diferencia entre modelos climáticos.
            </p>
          </div>
        </section>
      )}

      <section aria-label="Matriz de zonas 2050" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[300px] flex-1">
            <h2 className="font-display text-[26px] leading-8 font-extrabold">Matriz de zonas 2050</h2>
            <p className="text-sm text-on-surface-variant">Cruza la aptitud climática futura (ECOCROP) con el riesgo de enfermedad. Cada cantón cae en una de cuatro decisiones.</p>
          </div>
          <SegmentedButton label="Escenario de la matriz" value={future} onChange={setFuture} className="w-64"
            options={[{ value: "ssp245_2050", label: "SSP2-4.5" }, { value: "ssp585_2050", label: "SSP5-8.5" }]} />
        </div>
        <div className="grid gap-6 lg:grid-cols-[400px_minmax(0,1fr)]">
          <div className="relative h-[560px] overflow-hidden rounded-lg border border-outline-variant">
            <LossMap areas={geo} context={context} mode="zonas" zones={zoneMap} selectedId={id} theme={theme} onSelect={st.selectCanton}
              ariaLabel="Mapa de la Costa con la matriz de zonas 2050" />
          </div>
          <div className="flex flex-col gap-3">
            <ZoneMatrix counts={zones?.counts} theme={theme} highlight={id ? zoneMap.get(id) : undefined} highlightName={cmp?.area.name} />
            <p className="text-xs text-on-surface-muted">Números = cantones de la Costa en cada zona. El color del mapa repite el de cada cuadro y siempre va con su nombre e ícono.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
