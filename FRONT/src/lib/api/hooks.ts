"use client";
/**
 * Hooks de datos (SWR). Los resultados no cambian durante la sesión, así que se
 * cachean por clave (escenario, área…) y no se revalidan al volver a la pestaña.
 */
import useSWR, { type SWRConfiguration } from "swr";
import * as api from "./endpoints";
import type { AreaKind, ScenarioId } from "./types";

const opts: SWRConfiguration = {
  revalidateOnFocus: false,
  revalidateIfStale: false,
  keepPreviousData: true,
  dedupingInterval: 5 * 60_000,
};

export const useMeta = () => useSWR("meta", api.getMeta, opts);
export const useScenarios = () => useSWR("scenarios", api.getScenarios, opts);
export const useEnso = () => useSWR("enso/current", api.getEnsoCurrent, opts);
export const useRequirements = () => useSWR("crops/cacao/requirements", api.getRequirements, opts);

export const useAreas = (kind: AreaKind = "canton") =>
  useSWR(["areas", kind], ([, k]) => api.getAreas(k), opts);

export const useAreasGeojson = (kind: AreaKind = "canton") =>
  useSWR(["areas/geojson", kind], ([, k]) => api.getAreasGeojson(k), opts);

export const useLosses = (scenario: ScenarioId | null) =>
  useSWR(scenario ? ["losses", scenario] : null, ([, s]) => api.getLosses(s), opts);

export const useLossSummary = (scenario: ScenarioId, province?: string) =>
  useSWR(["losses/summary", scenario, province ?? ""], ([, s, p]) => api.getLossSummary(s, p || undefined), opts);

export const useAreaDetail = (id: string | null, scenario: ScenarioId) =>
  useSWR(id ? ["detail", id, scenario] : null, ([, i, s]) => api.getAreaDetail(i, s), opts);

export const useAreaStrategies = (id: string | null, scenario: ScenarioId) =>
  useSWR(id ? ["strategies", id, scenario] : null, ([, i, s]) => api.getAreaStrategies(i, s), opts);

export const useCompare = (id: string | null, scenarios: ScenarioId[]) =>
  useSWR(id ? ["compare", id, scenarios.join(",")] : null, ([, i]) => api.getCompare(i, scenarios), opts);

export const useZones = (future: ScenarioId | null) =>
  useSWR(future ? ["zones", future] : null, ([, f]) => api.getZones(f), opts);
