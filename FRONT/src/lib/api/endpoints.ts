/**
 * Endpoints del backend FastAPI (/api/v1). Uno por ruta de docs/08-api-contrato.md.
 * Todos son de solo lectura: la API sirve resultados precalculados por el ETL y el modelo.
 */
import * as adapt from "./adapt";
import { riskClassOf } from "@/lib/design/colors";
import { apiGet, buildUrl } from "./client";
import { mock } from "./mock";
import type { AlertsResponse, PointClimate, PointLookup,
  AreaDetail,
  AreaKind,
  AreaRef,
  AreasGeoJSON,
  CompareResponse,
  CropRequirements,
  EnsoCurrent,
  ExportFormat,
  LossSummary,
  LossesResponse,
  Meta,
  Scenario,
  ScenarioId,
  StrategiesResponse,
  ZonesResponse,
} from "./types";

export const getMeta = () => apiGet<Meta>("/meta", undefined, mock.meta, adapt.meta);

export const getScenarios = () => apiGet<Scenario[]>("/scenarios", undefined, mock.scenarios, adapt.scenarios);

export const getEnsoCurrent = () => apiGet<EnsoCurrent>("/enso/current", undefined, mock.ensoCurrent, adapt.enso);

export const getAreas = (kind: AreaKind = "canton", province?: string) =>
  apiGet<AreaRef[]>("/areas", { kind, province }, () => mock.areas(kind, province), adapt.areas);

export const getAreasGeojson = (kind: AreaKind = "canton", province?: string) =>
  apiGet<AreasGeoJSON>("/areas/geojson", { kind, province }, () => mock.areasGeojson(kind, province), (r) => adapt.areasGeojson(r, kind));

export const getRequirements = () =>
  apiGet<CropRequirements>("/crops/cacao/requirements", undefined, mock.requirements, adapt.requirements);

export const getLosses = (scenario: ScenarioId, kind: AreaKind = "canton", province?: string) =>
  apiGet<LossesResponse>("/losses", { scenario, kind, province }, () => mock.losses(scenario, kind, province), (r) => adapt.losses(r, kind));

export const getLossSummary = (scenario: ScenarioId, province?: string) =>
  apiGet<LossSummary>("/losses/summary", { scenario, province }, () => mock.lossSummary(scenario, province), async (r) =>
    // el reparto en 5 niveles sale de las pérdidas por cantón del mismo escenario y provincia
    adapt.summary(r, (await getLosses(scenario, "canton", province)).items));

// El detalle también lo usan estrategias y comparar: se reutiliza la misma petición unos minutos
const detailMemo = new Map<string, { at: number; p: Promise<AreaDetail> }>();
export const getAreaDetail = (id: string, scenario: ScenarioId): Promise<AreaDetail> => {
  const k = `${id}|${scenario}`;
  const hit = detailMemo.get(k);
  if (hit && Date.now() - hit.at < 5 * 60_000) return hit.p;
  const p = fetchAreaDetail(id, scenario);
  detailMemo.set(k, { at: Date.now(), p });
  p.catch(() => detailMemo.delete(k));
  return p;
};
const fetchAreaDetail = (id: string, scenario: ScenarioId) =>
  apiGet<AreaDetail>(`/areas/${encodeURIComponent(id)}/detail`, { scenario }, () => mock.areaDetail(id, scenario), adapt.detail);

export const getAreaStrategies = (id: string, scenario: ScenarioId) =>
  apiGet<StrategiesResponse>(`/areas/${encodeURIComponent(id)}/strategies`, { scenario }, () => mock.strategies(id, scenario), async (r) =>
    adapt.strategies(r, (await getAreaDetail(id, scenario)).loss?.loss_t ?? null));

export const getCompare = (areaId: string, scenarios: ScenarioId[]) =>
  apiGet<CompareResponse>("/compare", { area_id: areaId, scenarios }, () => mock.compare(areaId, scenarios), async (r) =>
    adapt.compare(r, (await getAreaDetail(areaId, scenarios[0] ?? "normal")).area));

export const getZones = (future: ScenarioId = "ssp245_2050") =>
  apiGet<ZonesResponse>("/zones", { future }, () => mock.zones(future), adapt.zones);

/**
 * Exportación para QGIS: el backend todavía no tiene GET /export, así que la capa
 * (GeoJSON + estilo .qml / .sld / CSV) se arma en el navegador con los datos que da la API.
 */
export const exportRunsInBrowser = () => true;

/** Por si el backend agrega /export más adelante. */
export function exportUrl(opts: { scenarios: ScenarioId[]; format: ExportFormat; crs: 4326 | 32717; level: AreaKind; zones?: boolean }): string {
  return buildUrl("/export", {
    scenarios: opts.scenarios, format: opts.format, crs: opts.crs, level: opts.level, zones: opts.zones ? "ssp245_2050" : undefined,
  });
}

/** ¿En qué cantón cae este punto? (404 si no cae en ninguno) */
export const lookupPoint = (lat: number, lon: number) =>
  apiGet<PointLookup>("/areas/lookup", { lat, lon }, () => mock.lookupPoint(lat, lon));

/** Clima de un punto (NASA POWER, celda ~55 km) + chequeo frente a lo que necesita el cacao */
export const getPointClimate = (lat: number, lon: number) =>
  apiGet<PointClimate>("/point/climate", { lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100 }, () => mock.pointClimate(lat, lon));

/**
 * Alertas en lenguaje natural (GET /alerts): las cifras las calcula el modelo; el LLM del backend
 * solo las redacta. Sin backend: texto automático con los datos de demostración.
 */
export const getAlerts = (scenario: ScenarioId, province?: string) =>
  apiGet<AlertsResponse>("/alerts", { scenario, province }, async () => {
    const l = await mock.losses(scenario, "canton", province);
    const areas = await mock.areas("canton", province);
    const byProv = new Map<string, { pcts: number[]; cantones: string[] }>();
    for (const a of areas) {
      const it = l.items.find((i) => i.area_id === a.id);
      if (!it) continue;
      const g = byProv.get(a.province) ?? { pcts: [], cantones: [] };
      g.pcts.push(it.loss_pct); g.cantones.push(a.name); byProv.set(a.province, g);
    }
    const items = [...byProv.entries()].map(([prov, g]) => {
      const pct = Math.round((g.pcts.reduce((x, y) => x + y, 0) / g.pcts.length) * 10) / 10;
      return { area_id: prov, provincia: prov, nivel: riskClassOf(pct), perdida_pct: pct,
        rango_pct: [Math.min(...g.pcts), Math.max(...g.pcts)] as [number, number], perdida_t: null, perdida_usd: null, vs_normal_pts: 0,
        factor_principal: null, cantones: g.cantones, evidencia: null, extrapolado: false, prob_perder_mas_20: null,
        titulo: `${prov}: pérdida promedio ${String(pct).replace(".", ",")} %`,
        mensaje: "Datos de demostración: conecte el backend para ver las alertas del modelo.",
        accion: "Revisar la ficha de cada cantón.", cuando: "Enero a junio." };
    }).sort((a, b) => b.perdida_pct - a.perdida_pct);
    return { scenario, province: province ?? null, resumen: "Datos de demostración.", items, generated_by: "plantilla", model: null, provider: null,
      disclaimer: "Apoya, no reemplaza, al técnico." } satisfies AlertsResponse;
  }, adapt.alerts);
