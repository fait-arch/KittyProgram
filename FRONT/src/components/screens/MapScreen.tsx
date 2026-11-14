"use client";
import dynamic from "next/dynamic";
import { useCallback, useMemo } from "react";
import useSWR from "swr";
import type { FeatureCollection } from "geojson";
import { useAreasGeojson, useLosses, useScenarios, useZones } from "@/lib/api/hooks";
import type { AreaProps, RiskClass, Zone } from "@/lib/api/types";
import { RISK_CLASSES, RISK_LABEL, riskClassOf, ZONE_COLORS, ZONE_META } from "@/lib/design/colors";
import { fmtPct, fmtT, fmtUsd } from "@/lib/design/format";
import { useMapState } from "@/lib/state/useMapState";
import { useTheme } from "@/lib/theme";
import { useDataSource } from "@/lib/api/client";
import { ControlPanel } from "@/components/organisms/ControlPanel";
import { SegmentedButton } from "@/components/molecules/SegmentedButton";
import { ScenarioSelector } from "@/components/molecules/ScenarioSelector";
import { AreaSheet } from "@/components/organisms/AreaSheet";
import { FilterChip } from "@/components/atoms/FilterChip";
import { Icon } from "@/components/atoms/Icon";
import { MapLegend } from "@/components/organisms/MapLegend";
import { LossTable } from "@/components/organisms/LossTable";

const EarthMap = dynamic(() => import("@/components/organisms/EarthMap"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 grid place-items-center text-on-surface-variant">Cargando globo…</div>,
});
const LossMap = dynamic(() => import("@/components/organisms/LossMap"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 grid place-items-center text-on-surface-variant">Cargando mapa…</div>,
});

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/** Pantalla principal: ¿cuánto cacao se pierde aquí con El Niño? */
export function MapScreen() {
  const st = useMapState();
  const { theme } = useTheme();
  const { mock } = useDataSource();
  const { data: scenarios } = useScenarios();
  const { data: geo } = useAreasGeojson("canton");
  const { data: context } = useSWR("geo/contexto", () => fetch("/geo/ecuador-contexto.geojson").then((r) => r.json() as Promise<FeatureCollection>), {
    revalidateOnFocus: false,
  });
  const { data: losses } = useLosses(st.scenario);
  const { data: zones } = useZones(st.layer === "zonas" || st.vista === "satelite" ? "ssp245_2050" : null);

  const areas = useMemo(() => new Map<string, AreaProps>(geo?.features.map((f) => [f.properties.id, f.properties]) ?? []), [geo]);
  const values = useMemo(() => new Map<string, number>(losses?.items.map((i) => [i.area_id, i.loss_pct]) ?? []), [losses]);
  const zoneMap = useMemo(() => new Map<string, Zone>(zones?.items.map((z) => [z.area_id, z.zone]) ?? []), [zones]);
  const lossCounts = useMemo(() => {
    const c = Object.fromEntries(RISK_CLASSES.map((k) => [k, 0])) as Record<RiskClass, number>;
    losses?.items.forEach((i) => c[i.risk_class]++);
    return c;
  }, [losses]);
  const scLabel = scenarios?.find((s) => s.id === st.scenario)?.label ?? st.scenario;

  const tooltip = useCallback(
    (p: AreaProps) => {
      if (st.layer === "zonas") {
        const z = zoneMap.get(p.id);
        return `<b>${esc(p.name)}</b> · ${esc(p.province)}<br>${z ? `Zona ${ZONE_META[z].label.toLowerCase()}` : "sin datos"}`;
      }
      const v = values.get(p.id);
      return `<b>${esc(p.name)}</b> · ${esc(p.province)}<br>${v != null ? `${fmtPct(v)} · pérdida ${RISK_LABEL[riskClassOf(v)].toLowerCase()}` : "sin datos"}`;
    },
    [values, zoneMap, st.layer],
  );

  const selectedLoss = st.canton ? losses?.items.find((i) => i.area_id === st.canton) : undefined;

  return (
    <div className="flex h-full">
      <ControlPanel
        scenario={st.scenario}
        onScenario={st.setScenario}
        scenarios={scenarios}
        province={st.province}
        onProvince={st.setProvince}
        items={losses?.items}
        areas={areas}
        selectedId={st.canton}
        onSelect={st.selectCanton}
        collapsed={!!st.canton}
      />

      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className={`border-b border-outline-variant bg-surface px-4 py-3 no-print ${st.canton ? "2xl:hidden" : "lg:hidden"}`}>
          <ScenarioSelector compact value={st.scenario} onChange={st.setScenario} scenarios={scenarios} />
        </div>
        <div className="relative min-h-0 flex-1">
          {st.vista === "satelite" ? (
            <EarthMap areas={geo} values={values} zones={zones?.items} mode={st.layer} selectedId={st.canton} onSelect={st.selectCanton} theme={theme}
              ariaLabel={`Globo satelital con la Costa de Ecuador: ${st.layer === "zonas" ? "matriz de zonas 2050" : `pérdida estimada de cacao, ${scLabel}`}; mazorcas en cantones aptos para sembrar`} />
          ) : (
          <LossMap
            areas={geo}
            context={context}
            mode={st.layer}
            values={values}
            zones={zoneMap}
            selectedId={st.canton}
            dimProvince={st.province}
            onSelect={st.selectCanton}
            tooltip={tooltip}
            theme={theme}
            ariaLabel={`Mapa de la Costa de Ecuador: ${st.layer === "zonas" ? "matriz de zonas 2050" : `pérdida estimada de cacao por cantón, ${scLabel}`}`}
            attribution={mock ? "Límites: pabl-o-ce/ecuador-geojson (MIT) · datos de demostración" : "Límites: FAO GAUL · Datos: NASA, Copernicus, NOAA, INEC, FAO"}
          />
          )}

          <div className="absolute top-4 right-20 left-4 z-[800] flex flex-wrap items-center gap-2 no-print">
            <SegmentedButton label="Tipo de mapa" value={st.vista} onChange={st.setVista} className="w-[232px] bg-surface/95 shadow-sm backdrop-blur"
              options={[{ value: "2d", label: "Mapa 2D" }, { value: "satelite", label: "Satélite 3D" }]} />
            <SegmentedButton label="Qué mostrar" value={st.layer} onChange={st.setLayer} className="w-[232px] bg-surface/95 shadow-sm backdrop-blur"
              options={[{ value: "perdida", label: "Pérdida" }, { value: "zonas", label: "Zonas 2050" }]} />
            <button type="button" onClick={() => st.setTableOpen(true)} title="Ver los datos del mapa como tabla"
              className="state-layer inline-flex h-10 items-center gap-1.5 rounded-full border border-outline bg-surface/95 px-4 text-sm font-semibold text-on-surface shadow-sm backdrop-blur cursor-pointer">
              <Icon name="table_rows" size={18} />Tabla
            </button>
          </div>

          <div className={`absolute z-[800] hidden sm:block ${st.vista === "satelite" ? "right-4 bottom-10" : "bottom-6 left-4"}`}>
            {st.vista === "satelite" && (
              <div className="mb-2 w-[248px] rounded-lg border border-outline-variant bg-surface-low p-3 text-[13px] shadow-lg">
                <b className="mb-1 block font-display text-sm">Mazorcas: dónde sembrar</b>
                <span className="mb-1.5 block text-xs text-on-surface-variant">Cantones con aptitud ECOCROP alta (≥ 0,7); el color es la zona 2050.</span>
                {(["segura", "manejo"] as const).map((z) => (
                  <span key={z} className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-full ring-2 ring-white" style={{ background: ZONE_COLORS[theme][z] }} />{ZONE_META[z].label} · {ZONE_META[z].quadrant}</span>
                ))}
              </div>
            )}
            <MapLegend mode={st.layer} theme={theme} scenarioLabel={st.layer === "zonas" ? "SSP2-4.5 · aptitud × riesgo" : scLabel} lossCounts={lossCounts} zoneCounts={zones?.counts} />
          </div>

          {!st.canton && (
            <div className="absolute inset-x-3 bottom-3 z-[800] flex items-center gap-3 rounded-lg bg-surface-high p-3 shadow-lg lg:hidden">
              <Icon name="touch_app" className="text-primary" />
              <span className="text-sm">Toca un cantón para ver cuánto se pierde y qué hacer.</span>
            </div>
          )}
          {st.canton && selectedLoss && (
            <span className="sr-only" aria-live="polite">
              {areas.get(st.canton)?.name}: {fmtPct(selectedLoss.loss_pct)}, {fmtT(selectedLoss.loss_t)}, {fmtUsd(selectedLoss.loss_usd)}
            </span>
          )}
        </div>
      </div>

      {st.canton && <AreaSheet key={st.canton} id={st.canton} scenario={st.scenario} onClose={() => st.selectCanton(null)} />}

      <LossTable
        open={st.tableOpen}
        onClose={() => st.setTableOpen(false)}
        items={losses?.items ?? []}
        areas={areas}
        scenarioLabel={scLabel}
        onSelect={(id) => st.patch({ canton: id, tabla: null })}
      />
    </div>
  );
}
