/**
 * Endpoints del backend FastAPI (/api/v1). Uno por ruta de docs/08-api-contrato.md.
 * Todos son de solo lectura: la API sirve resultados precalculados por el ETL y el modelo.
 */
import { apiGet, buildUrl, DATA_MODE } from "./client";
import { mock } from "./mock";
import type { PointClimate, PointLookup,
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

export const getMeta = () => apiGet<Meta>("/meta", undefined, mock.meta);

export const getScenarios = () => apiGet<Scenario[]>("/scenarios", undefined, mock.scenarios);

export const getEnsoCurrent = () => apiGet<EnsoCurrent>("/enso/current", undefined, mock.ensoCurrent);

export const getAreas = (kind: AreaKind = "canton", province?: string) =>
  apiGet<AreaRef[]>("/areas", { kind, province }, () => mock.areas(kind, province));

export const getAreasGeojson = (kind: AreaKind = "canton", province?: string) =>
  apiGet<AreasGeoJSON>("/areas/geojson", { kind, province }, () => mock.areasGeojson(kind, province));

export const getRequirements = () =>
  apiGet<CropRequirements>("/crops/cacao/requirements", undefined, mock.requirements);

export const getLosses = (scenario: ScenarioId, kind: AreaKind = "canton", province?: string) =>
  apiGet<LossesResponse>("/losses", { scenario, kind, province }, () => mock.losses(scenario, kind, province));

export const getLossSummary = (scenario: ScenarioId, province?: string) =>
  apiGet<LossSummary>("/losses/summary", { scenario, province }, () => mock.lossSummary(scenario, province));

export const getAreaDetail = (id: string, scenario: ScenarioId) =>
  apiGet<AreaDetail>(`/areas/${encodeURIComponent(id)}/detail`, { scenario }, () => mock.areaDetail(id, scenario));

export const getAreaStrategies = (id: string, scenario: ScenarioId) =>
  apiGet<StrategiesResponse>(`/areas/${encodeURIComponent(id)}/strategies`, { scenario }, () => mock.strategies(id, scenario));

export const getCompare = (areaId: string, scenarios: ScenarioId[]) =>
  apiGet<CompareResponse>("/compare", { area_id: areaId, scenarios }, () => mock.compare(areaId, scenarios));

export const getZones = (future: ScenarioId = "ssp245_2050") =>
  apiGet<ZonesResponse>("/zones", { future }, () => mock.zones(future));

/** URL de descarga del archivo para QGIS (GeoPackage con estilo, GeoJSON/SHP + QML, SLD). */
export function exportUrl(opts: {
  scenarios: ScenarioId[];
  format: ExportFormat;
  crs: 4326 | 32717;
  level: AreaKind;
  zones?: boolean;
}): string {
  return buildUrl("/export", {
    scenarios: opts.scenarios,
    format: opts.format,
    crs: opts.crs,
    level: opts.level,
    zones: opts.zones ? "ssp245_2050" : undefined,
  });
}

/** En modo demostración la exportación se arma en el navegador (GeoJSON + QML / SLD / CSV). */
export const exportRunsInBrowser = () => DATA_MODE === "mock";

/** ¿En qué cantón cae este punto? (404 si no cae en ninguno) */
export const lookupPoint = (lat: number, lon: number) =>
  apiGet<PointLookup>("/areas/lookup", { lat, lon }, () => mock.lookupPoint(lat, lon));

/** Clima de un punto (NASA POWER, celda ~55 km) + chequeo frente a lo que necesita el cacao */
export const getPointClimate = (lat: number, lon: number) =>
  apiGet<PointClimate>("/point/climate", { lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100 }, () => mock.pointClimate(lat, lon));
