"use client";
import { useMemo } from "react";
import useSWR from "swr";
import type { FeatureCollection } from "geojson";
import { useAreaDetail, useAreaStrategies, useAreasGeojson, useEnso, useLosses, useScenarios } from "@/lib/api/hooks";
import type { ScenarioId } from "@/lib/api/types";

/** Datos comunes de las plantillas: los mismos endpoints que el panel del cantón. */
export function useTemplateData(canton: string, scenario: ScenarioId) {
  const detail = useAreaDetail(canton, scenario);
  const strategies = useAreaStrategies(canton, scenario);
  const { data: scenarios } = useScenarios();
  const { data: enso } = useEnso();
  const { data: geo } = useAreasGeojson("canton");
  const { data: losses } = useLosses(scenario);
  const { data: context } = useSWR("geo/contexto", () => fetch("/geo/ecuador-contexto.geojson").then((r) => r.json() as Promise<FeatureCollection>), { revalidateOnFocus: false });
  const values = useMemo(() => new Map((losses?.items ?? []).map((i) => [i.area_id, i.loss_pct])), [losses]);
  const sc = scenarios?.find((s) => s.id === scenario);
  return { d: detail.data, error: detail.error, strategies: strategies.data, scenarios, sc, scenarioLabel: sc?.label ?? scenario, enso, geo, context, values };
}

export const today = () => new Intl.DateTimeFormat("es-EC", { day: "numeric", month: "long", year: "numeric" }).format(new Date());
