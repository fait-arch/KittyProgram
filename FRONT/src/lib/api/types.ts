/**
 * Contrato con el backend FastAPI (/api/v1). Espejo de los modelos Pydantic de
 * docs/08-api-contrato.md: si cambia uno, cambia el otro.
 */
import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";

export type ScenarioId = "normal" | "nino" | "nino_extremo" | "nina" | "actual" | "ssp245_2050" | "ssp585_2050";
export type AreaKind = "province" | "canton";
export type RiskClass = "baja" | "moderada" | "alta" | "muy_alta" | "critica";
export type Zone = "segura" | "manejo" | "transicion" | "critica";
export type ExportFormat = "gpkg" | "geojson" | "shp" | "sld";

export interface Scenario {
  id: ScenarioId;
  label: string;
  group: "hoy" | "2050";
  phase: 1 | 2;
  description: string;
  available: boolean;
  /** true si el modelo se aplica fuera del clima con que se entrenó (2050) */
  extrapolation: boolean;
}

export interface EnsoCurrent {
  phase: "nino" | "nina" | "neutro";
  strength: "debil" | "moderado" | "fuerte" | "muy_fuerte" | null;
  oni: { value: number; season: string; year: number };
  nino12: { anomaly_c: number; month: string };
  event_in_progress: boolean;
  source: string;
  updated_at: string;
}

export interface AreaRef {
  id: string;
  name: string;
  province: string;
  kind: AreaKind;
  cacao_ha: number | null;
}

export interface AreaProps {
  id: string;
  name: string;
  province: string;
  kind: AreaKind;
}
export type AreasGeoJSON = FeatureCollection<Polygon | MultiPolygon, AreaProps>;

export interface LossItem {
  area_id: string;
  loss_pct: number;
  loss_pct_low: number;
  loss_pct_high: number;
  loss_t: number | null;
  loss_usd: number | null;
  risk_class: RiskClass;
  /** "validado_nacional" | "indice_subnacional_no_validado" (modelo de ML) */
  evidence?: string | null;
  /** clima más extremo que cualquier año de entrenamiento */
  extrapolated?: boolean;
  /** probabilidad (0–1) de perder más del 20 % */
  prob_loss_gt20?: number | null;
  /** el cantón usa el índice de esta provincia (el modelo se entrena por provincia) */
  inherited_from?: string | null;
}

export interface LossesResponse {
  scenario: ScenarioId;
  kind: AreaKind;
  model: string;
  items: LossItem[];
}

export interface LossSummary {
  scenario: ScenarioId;
  province: string | null;
  loss_t: number;
  loss_usd: number;
  vs_normal: { loss_t: number; loss_usd: number } | null;
  n_areas: number;
  areas_by_class: Record<RiskClass, number>;
}

export interface Factor {
  feature: string;
  /** Texto para productores ("Días húmedos y templados…") */
  label: string;
  value: number;
  unit: string;
  /** Puntos porcentuales de pérdida que aporta (SHAP o coeficiente × desvío) */
  contribution_pct: number;
  source: string;
}

export interface MonthlyRisk {
  month: number; // 1–12
  monilia: number; // 0–1
  phytophthora: number; // 0–1
}

export interface Suitability {
  score: number; // 0–1 (ECOCROP)
  class: "apta" | "marginal" | "no_apta";
  limiting_factors: string[];
}

export interface AreaClimate {
  temp_mean_c: number | null;
  rain_annual_mm: number | null;
  elevation_m: number | null;
  soil_ph: number | null;
}

/** Datos del modelo; mae y años quedan en null si el backend aún no tiene un modelo entrenado */
export interface ModelInfo {
  name: string;
  mae: number | null;
  trained_years: [number | null, number | null];
}

export interface AreaDetail {
  area: AreaRef;
  scenario: ScenarioId;
  /** null si el modelo no tiene estimación para esta área y escenario */
  loss: (LossItem & {
    vs_normal: { loss_pct: number; delta_pct: number; delta_usd: number } | null;
  }) | null;
  top_factors: Factor[];
  monthly_risk: MonthlyRisk[];
  suitability: Suitability;
  climate: AreaClimate;
  model: ModelInfo;
  disclaimer: string;
  data_gaps?: string[];
}

export interface RequirementParam {
  id: "temp_mean" | "rain_annual" | "elevation" | "soil_ph";
  label: string;
  unit: string;
  optimal_min: number | null;
  optimal_max: number | null;
  absolute_min: number | null;
  absolute_max: number | null;
}

export interface CropRequirements {
  crop: "cacao";
  source: string;
  parameters: RequirementParam[];
}

export interface Strategy {
  id: "sanitario" | "drenaje_sombra" | "diversificacion";
  rank: number;
  name: string;
  summary: string;
  expected_loss_pct: number;
  avoided_loss_t: number | null;
  avoided_loss_usd: number | null;
  protects_income: boolean;
  why: string;
  evidence: string;
  data_gaps: string;
  risks: string;
}

export interface StrategiesResponse {
  area_id: string;
  scenario: ScenarioId;
  baseline_loss_pct: number;
  items: Strategy[];
}

export interface CompareItem {
  scenario: ScenarioId;
  loss: LossItem;
  suitability: Suitability;
  extrapolation: boolean;
}

export interface CompareResponse {
  area: AreaRef;
  items: CompareItem[];
}

export interface ZoneItem {
  area_id: string;
  zone: Zone;
  suitability_score: number;
  risk_index: number;
}

export interface ZonesResponse {
  future: ScenarioId;
  counts: Record<Zone, number>;
  items: ZoneItem[];
}

export interface DataSource {
  id: string;
  name: string;
  provider: string;
  use: string;
}

export interface Meta {
  sources: DataSource[];
  model: ModelInfo & {
    skill_vs_baseline: number | null;
    interval_coverage: number | null;
    note?: string | null;
    algorithm?: string | null;
    n_samples?: number | null;
    /** validación «dejando un año fuera» (ficha del modelo de ML) */
    validation?: { corr: number | null; r2: number | null; p: number | null; province_corr: number | null; province_p: number | null; nino_years_hit: string[] } | null;
  };
  limitations?: string[];
  disclaimer?: string;
  /** "supabase" | "mock" según BACK/.env (DATA_SOURCE) */
  data_source?: string | null;
  updated_at: string;
}

/** Error estándar de FastAPI */
export interface ApiErrorBody {
  detail: string | { loc: (string | number)[]; msg: string; type: string }[];
}

// --- Mi finca (BACK/app/routers: /areas/lookup y /point/climate) ---
export interface PointLookup {
  canton: { id: string; name: string };
  province: { id: string; name: string } | null;
}
export interface PointRequirementCheck {
  parameter: string;
  label: string;
  value: number | null;
  unit: string | null;
  opt: [number | null, number | null];
  abs: [number | null, number | null];
  status: "ok" | "warn" | "out" | "sin_dato";
}
export interface PointClimate {
  point: { lat: number; lon: number };
  elevation_m: number | null;
  source: string;
  resolution_km: number;
  annual: { t2m: number | null; rh2m: number | null; precip_mm: number | null };
  precip_mm_month?: Record<string, number>;
  requirement_check: PointRequirementCheck[];
  warning?: string;
}

// --- Alertas en lenguaje natural (GET /alerts) ---
export interface AlertItem {
  area_id: string;
  provincia: string;
  nivel: RiskClass;
  perdida_pct: number;
  rango_pct: [number | null, number | null];
  perdida_t: number | null;
  perdida_usd: number | null;
  vs_normal_pts: number;
  factor_principal: string | null;
  cantones: string[];
  evidencia: string | null;
  extrapolado: boolean;
  prob_perder_mas_20: number | null;
  titulo: string;
  mensaje: string;
  accion: string;
  cuando: string;
}
export interface AlertsResponse {
  scenario: ScenarioId;
  province: string | null;
  resumen: string;
  items: AlertItem[];
  /** "ia" (redactado por el LLM) o "plantilla" (texto automático con los mismos datos) */
  generated_by: "ia" | "plantilla";
  model: string | null;
  provider: string | null;
  disclaimer: string;
}
