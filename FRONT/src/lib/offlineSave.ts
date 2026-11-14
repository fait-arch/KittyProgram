"use client";
/**
 * «Guardar para usar sin conexión»: pide una vez todos los datos del cantón en los 5 escenarios.
 * El service worker guarda cada respuesta; luego la app la encuentra aunque no haya señal.
 */
import * as api from "@/lib/api/endpoints";
import type { ScenarioId } from "@/lib/api/types";
import { markCantonSaved } from "@/lib/offline";

const ALL: ScenarioId[] = ["normal", "nino", "actual", "ssp245_2050", "ssp585_2050"];

export async function saveCantonOffline(id: string, name: string, onProgress?: (done: number, total: number) => void) {
  const jobs: (() => Promise<unknown>)[] = [
    () => api.getScenarios(), () => api.getEnsoCurrent(), () => api.getMeta(), () => api.getRequirements(),
    () => api.getAreas("canton"), () => api.getAreasGeojson("canton"), () => api.getCompare(id, ["normal", "nino", "ssp245_2050", "ssp585_2050"]),
    () => api.getZones("ssp245_2050"),
    ...ALL.flatMap((s) => [() => api.getAreaDetail(id, s), () => api.getAreaStrategies(id, s), () => api.getLosses(s), () => api.getLossSummary(s)]),
    () => fetch("/geo/ecuador-contexto.geojson"),
    ...["/", "/comparar", "/finca", "/metodologia", "/plantillas"].map((r) => () => fetch(r)),
  ];
  let done = 0;
  const results = await Promise.allSettled(jobs.map((j) => j().finally(() => onProgress?.(++done, jobs.length))));
  const failed = results.filter((r) => r.status === "rejected").length;
  if (failed < jobs.length) markCantonSaved({ id, name });
  return { total: jobs.length, failed };
}
