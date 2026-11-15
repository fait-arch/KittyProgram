/**
 * Traductor del contrato real del backend FastAPI (BACK/app/routers) al que usan las pantallas
 * (types.ts). Así las pantallas no cambian si el backend agrega campos, y todo lo que se ve
 * viene del backend: nada se inventa aquí, solo se renombra, se calcula a partir de lo recibido
 * (p. ej. la clase de 5 niveles desde loss_pct) o se deja vacío (null) si el backend no lo envía.
 */
import { RISK_CLASSES, riskClassOf } from "@/lib/design/colors";
import type {
  AreaDetail, AreaKind, AreaRef, AreasGeoJSON, CompareResponse, CropRequirements, EnsoCurrent, Factor,
  AlertsResponse, LossItem, LossSummary, LossesResponse, Meta, RequirementParam, RiskClass, Scenario, ScenarioId,
  StrategiesResponse, Strategy, Suitability, Zone, ZonesResponse,
} from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Raw = any;

// --- Nombres de provincia: el backend los guarda sin tildes ("Los Rios"); la interfaz los muestra con tildes ---
const norm = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const PROVINCE_NAME: Record<string, string> = Object.fromEntries(
  ["Los Ríos", "Manabí", "Guayas", "Esmeraldas", "El Oro", "Santa Elena", "Azuay", "Bolívar", "Cañar", "Carchi",
    "Chimborazo", "Cotopaxi", "Imbabura", "Loja", "Pichincha", "Tungurahua", "Galápagos", "Morona Santiago", "Napo",
    "Orellana", "Pastaza", "Sucumbíos", "Zamora Chinchipe"].map((n) => [norm(n), n]),
);
PROVINCE_NAME[norm("Santo Domingo de los Tsáchilas")] = "Santo Domingo";
PROVINCE_NAME[norm("Santo Domingo")] = "Santo Domingo";
export const provinceName = (raw: unknown): string => {
  const s = typeof raw === "string" ? raw : (raw as { name?: string } | null)?.name ?? "";
  return PROVINCE_NAME[norm(s)] ?? s;
};

const KNOWN_SCENARIOS: ScenarioId[] = ["normal", "nino", "nino_extremo", "nina", "actual", "ssp245_2050", "ssp585_2050"];
/** Textos de escenario sugeridos por el equipo de ML (se usan si el backend no trae descripción propia) */
const SCENARIO_TEXT: Partial<Record<ScenarioId, string>> = {
  normal: "Año sin El Niño: pérdida mínima.",
  nino: "«Año Niño» según el índice ONI 2001–2025. Esos Niños casi no trajeron lluvia extrema a la Costa: la pérdida es baja.",
  nino_extremo: "Un Niño costero como 1983 o 1998, con lluvia extrema durante meses en la Costa.",
  nina: "Año con La Niña (Pacífico más frío).",
  actual: "Temporada 2027. Hoy el mar frente a Ecuador está más caliente que en 1997. De los años parecidos, uno fue desastre (1998) y dos no (2016, 2024): rango amplio.",
  ssp245_2050: "En preparación: proyecciones CMIP6 (emisiones moderadas). Leer como tendencia.",
  ssp585_2050: "En preparación: proyecciones CMIP6 (emisiones altas). Leer como tendencia.",
};
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

// --- Catálogos ---
export const scenarios = (r: Raw[]): Scenario[] =>
  r.filter((s) => KNOWN_SCENARIOS.includes(s.id)).map((s) => ({
    id: s.id,
    label: s.name_es ?? s.label ?? s.id,
    group: s.kind === "projection" ? "2050" : "hoy",
    phase: s.phase === 2 ? 2 : 1,
    description: SCENARIO_TEXT[s.id as ScenarioId] ?? s.description ?? "",
    available: s.available !== false,
    extrapolation: s.kind === "projection",
  }));

export const enso = (r: Raw): EnsoCurrent => ({
  phase: r.phase === "nino" || r.phase === "nina" ? r.phase : "neutro",
  strength: r.intensity ?? null,
  oni: { value: r.oni?.value ?? 0, season: r.oni?.season ?? "", year: Number(String(r.oni?.month ?? "").slice(0, 4)) || new Date().getFullYear() },
  nino12: { anomaly_c: r.nino12_anom?.value ?? 0, month: r.nino12_anom?.month ?? "" },
  event_in_progress: !!r.event && !r.event.end_month,
  source: r.source ?? "NOAA CPC",
  updated_at: r.nino12_anom?.month ?? r.oni?.month ?? "",
});

const fmtRes = (m: number | null) => (m == null ? "" : m >= 1000 ? `celda de ~${Math.round(m / 1000)} km` : `celda de ${m} m`);
export const meta = (r: Raw): Meta => {
  const m = r.model ?? {};
  return {
    sources: (r.sources ?? []).map((s: Raw) => ({
      id: s.id, name: s.name, provider: s.provider,
      use: (r.variables ?? []).filter((v: Raw) => v.source_id === s.id).map((v: Raw) => v.name).join(", ") || fmtRes(s.spatial_res_m),
    })),
    model: {
      name: m.name ?? "—",
      mae: num(m.metrics?.mae),
      skill_vs_baseline: num(m.metrics?.skill_vs_baseline),
      interval_coverage: num(m.metrics?.interval_coverage ?? m.metrics?.interval_coverage_p10_p90),
      trained_years: [m.train_start_year ?? null, m.train_end_year ?? null],
      note: m.metrics?.note ?? null,
      algorithm: m.algorithm ?? null,
      n_samples: num(m.n_samples),
      validation: m.metrics?.corr != null ? {
        corr: num(m.metrics.corr), r2: num(m.metrics.r2_oos), p: num(m.metrics.permutation_p),
        province_corr: num(m.metrics.province_skill), province_p: num(m.metrics.permutation_p_province),
        nino_years_hit: Object.entries(m.metrics.nino_years_hit ?? {}).filter(([, v]) => v).map(([k]) => k),
      } : null,
    },
    limitations: r.limitations ?? [],
    disclaimer: r.disclaimer ?? "",
    data_source: r.data_source ?? null,
    updated_at: m.created_at ?? "",
  };
};

const REQ_ID: Record<string, RequirementParam["id"]> = { temp_mean: "temp_mean", rain_annual: "rain_annual", altitude: "elevation", ph: "soil_ph" };
export const requirements = (r: Raw): CropRequirements => ({
  crop: "cacao",
  source: r.source ?? "ECOCROP",
  parameters: (r.numeric ?? []).filter((p: Raw) => REQ_ID[p.parameter]).map((p: Raw) => ({
    id: REQ_ID[p.parameter], label: p.label, unit: p.unit,
    optimal_min: p.opt_min ?? null, optimal_max: p.opt_max ?? null, absolute_min: p.abs_min ?? null, absolute_max: p.abs_max ?? null,
  })),
});

// --- Áreas ---
export const areaRef = (a: Raw): AreaRef => ({
  id: a.id, name: a.kind === "province" ? provinceName(a.name) : a.name,
  province: provinceName(a.kind === "province" ? a.name : a.province), kind: a.kind ?? "canton", cacao_ha: a.crop_ha ?? null,
});
export const areas = (r: Raw[]): AreaRef[] => r.map(areaRef);
// --- Límites territoriales reales (public/geo/territorio.geojson, sacado de supabase/seed/data/01_territorio.sql) ---
// El backend en modo de prueba dibuja cada cantón como un cuadrado; aquí se reemplaza por su límite oficial,
// buscando por id y, si no coincide, por nombre de cantón + provincia (sin tildes ni artículos: «El Empalme» = «Empalme»).
type TerrFeature = { properties: { id: string; kind: string; name: string; province?: string | null }; geometry: unknown };
const key = (s: unknown) => norm(String(s ?? "")).replace(/[^a-z0-9 ]/g, " ").replace(/^(el|la|los|las) /, "").replace(/\s+/g, " ").trim();
const provKey = (s: unknown) => key(provinceName(s));
let terrP: Promise<{ byId: Map<string, TerrFeature>; byName: Map<string, TerrFeature>; byCanton: Map<string, TerrFeature[]> }> | null = null;
export const loadTerritory = () =>
  (terrP ??= fetch("/geo/territorio.geojson")
    .then((r) => (r.ok ? r.json() : { features: [] }))
    .catch(() => ({ features: [] }))
    .then((g: { features: TerrFeature[] }) => {
      const byId = new Map<string, TerrFeature>(), byName = new Map<string, TerrFeature>(), byCanton = new Map<string, TerrFeature[]>();
      for (const f of g.features) {
        const p = f.properties;
        byId.set(p.id, f);
        byName.set(`${p.kind}|${key(p.name)}|${p.kind === "canton" ? provKey(p.province) : ""}`, f);
        if (p.kind === "canton") byCanton.set(key(p.name), [...(byCanton.get(key(p.name)) ?? []), f]);
      }
      return { byId, byName, byCanton };
    }));

export const areasGeojson = async (r: Raw, kind: AreaKind = "canton"): Promise<AreasGeoJSON> => {
  const t = await loadTerritory();
  const real = (p: Raw): TerrFeature | undefined => {
    const k = p?.kind ?? kind;
    if (t.byId.get(p?.id)?.properties.kind === k) return t.byId.get(p.id);
    const prov = k === "canton" ? provKey(p?.province) : "";
    const hit = t.byName.get(`${k}|${key(p?.name)}|${prov}`);
    if (hit) return hit;
    const same = k === "canton" ? t.byCanton.get(key(p?.name)) : undefined;
    return same?.length === 1 ? same[0] : undefined;
  };
  return {
    ...r,
    features: (r.features ?? []).map((f: Raw) => ({
      ...f,
      geometry: real(f.properties)?.geometry ?? f.geometry,
      properties: { ...f.properties, province: provinceName(f.properties?.province ?? (f.properties?.kind === "province" ? f.properties?.name : "")) },
    })),
  };
};

// --- Pérdidas (la clase de 5 niveles se calcula con la escala de la interfaz) ---
const modelInfo = (m: Raw) => ({
  name: m?.name ?? "—",
  mae: num(m?.mae ?? m?.metrics?.mae),
  trained_years: [m?.trained_years?.[0] ?? m?.train_start_year ?? null, m?.trained_years?.[1] ?? m?.train_end_year ?? null] as [number | null, number | null],
});
export const lossItem = (i: Raw, areaId?: string): LossItem => ({
  area_id: i.area_id ?? areaId,
  loss_pct: i.loss_pct,
  loss_pct_low: i.loss_pct_low ?? i.loss_pct,
  loss_pct_high: i.loss_pct_high ?? i.loss_pct,
  loss_t: num(i.loss_t),
  loss_usd: num(i.loss_usd),
  risk_class: riskClassOf(i.loss_pct),
  evidence: i.evidence ?? null,
  extrapolated: !!i.extrapolated,
  prob_loss_gt20: num(i.prob_loss_gt20),
  inherited_from: i.inherited_from ? provinceName(i.inherited_from) : null,
});
export const losses = (r: Raw, kind: AreaKind): LossesResponse => ({
  scenario: r.scenario, kind, model: r.model?.name ?? "—", items: (r.items ?? []).map((i: Raw) => lossItem(i)),
});

export const byClass = (items: { loss_pct: number }[]) => {
  const c = Object.fromEntries(RISK_CLASSES.map((k) => [k, 0])) as Record<RiskClass, number>;
  for (const i of items) c[riskClassOf(i.loss_pct)]++;
  return c;
};
/** El resumen del backend agrupa en 4 clases: el reparto de 5 niveles se arma con /losses del mismo escenario. */
export const summary = (r: Raw, items: { loss_pct: number }[]): LossSummary => ({
  scenario: r.scenario,
  province: r.scope?.kind === "province" ? provinceName(r.scope.name) : null,
  loss_t: r.totals?.loss_t ?? 0,
  loss_usd: r.totals?.loss_usd ?? 0,
  vs_normal: r.vs && r.scenario !== "normal" ? { loss_t: r.vs.delta_t ?? 0, loss_usd: r.vs.delta_usd ?? 0 } : null,
  n_areas: items.length,
  areas_by_class: byClass(items),
});

// --- Detalle del cantón ---
const FACTOR_UNIT: Record<string, string> = {
  fav_days_monilia: "días (ene–jun)", fav_days_phytophthora: "días (ene–jun)", heavy_rain_days: "días", saturated_days: "días",
  nino12_anom_jan_jun: "°C", oni_jan_jun: "°C", suitability_now: "",
};
const FACTOR_SOURCE: Record<string, string> = {
  fav_days_monilia: "ERA5-Land", fav_days_phytophthora: "ERA5-Land", heavy_rain_days: "NASA GPM IMERG", saturated_days: "NASA SMAP",
  nino12_anom_jan_jun: "NOAA CPC", oni_jan_jun: "NOAA CPC", suitability_now: "ECOCROP",
};
const factor = (f: Raw): Factor => ({
  feature: f.feature, label: f.label, value: f.value, unit: f.unit ?? FACTOR_UNIT[f.feature] ?? "",
  contribution_pct: f.contribution_pct, source: f.source ?? FACTOR_SOURCE[f.feature] ?? "",
});
const suitability = (s: Raw): Suitability => ({
  score: s?.score ?? 0, class: s?.class ?? "no_apta", limiting_factors: s?.limiting_factors ?? [],
});
const reqValue = (r: Raw, p: string) => num((r.requirement_check ?? []).find((c: Raw) => c.parameter === p)?.value);

export const detail = (r: Raw): AreaDetail => ({
  area: areaRef({ ...r.area, crop_ha: r.area?.crop_ha ?? r.loss?.exposed_ha }),
  scenario: r.scenario,
  loss: r.loss ? { ...lossItem(r.loss, r.area?.id), vs_normal: r.loss.vs_normal ?? null } : null,
  top_factors: (r.top_factors ?? []).map(factor),
  monthly_risk: (r.monthly_risk ?? []).map((m: Raw) => ({ month: m.month, monilia: m.monilia ?? 0, phytophthora: m.phytophthora ?? 0 })),
  suitability: suitability(r.suitability),
  climate: {
    temp_mean_c: num(r.climate?.t2m?.annual) ?? reqValue(r, "temp_mean"),
    rain_annual_mm: reqValue(r, "rain_annual") ?? num(r.climate?.precip?.annual),
    elevation_m: num(r.static?.elevation_mean_m) ?? reqValue(r, "altitude"),
    soil_ph: num(r.static?.soil_ph) ?? reqValue(r, "ph"),
  },
  model: modelInfo(r.model),
  disclaimer: r.disclaimer ?? "",
  data_gaps: r.data_gaps ?? [],
});

// --- Estrategias: el backend incluye la práctica actual (is_current) como referencia; se muestran las 3 alternativas ---
const STRAT_IDS = ["sanitario", "drenaje_sombra", "diversificacion"];
const list = (v: unknown) => (Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : (x as Raw).statement ?? "")).filter(Boolean).join(" ") : String(v ?? ""));
export const strategies = (r: Raw, lossT: number | null): StrategiesResponse => {
  const items: Strategy[] = (r.items ?? [])
    .filter((s: Raw) => !s.is_current && STRAT_IDS.includes(s.strategy_id))
    .sort((a: Raw, b: Raw) => (a.rank ?? 0) - (b.rank ?? 0))
    .map((s: Raw, i: number) => {
      const share = r.baseline_loss_pct ? Math.max(0, (r.baseline_loss_pct - s.expected_loss_pct) / r.baseline_loss_pct) : 0;
      return {
        id: s.strategy_id,
        rank: i + 1,
        name: s.name_es ?? s.name,
        summary: s.description ?? "",
        expected_loss_pct: s.expected_loss_pct,
        avoided_loss_t: lossT != null ? lossT * share : null,
        avoided_loss_usd: num(s.avoided_loss_usd),
        protects_income: (s.targets ?? []).some((t: Raw) => t.target === "ingreso") || (s.income_protected_usd ?? 0) > 0,
        why: s.why ?? "",
        evidence: list(s.evidence),
        data_gaps: list(s.data_gaps),
        risks: list(s.risks),
      };
    });
  return { area_id: r.area_id, scenario: r.scenario, baseline_loss_pct: r.baseline_loss_pct, items };
};

// --- Comparar escenarios y zonas 2050 ---
export const compare = (r: Raw, area: AreaRef): CompareResponse => ({
  area,
  items: (r.items ?? []).filter((i: Raw) => KNOWN_SCENARIOS.includes(i.scenario) && i.loss).map((i: Raw) => ({
    scenario: i.scenario,
    loss: lossItem(i.loss, r.area_id),
    suitability: suitability(i.suitability),
    extrapolation: String(i.scenario).startsWith("ssp"),
  })),
});

const ZONES: Zone[] = ["segura", "manejo", "transicion", "critica"];
export const zones = (r: Raw): ZonesResponse => {
  const items = (r.items ?? []).filter((z: Raw) => ZONES.includes(z.zone_class ?? z.zone)).map((z: Raw) => ({
    area_id: z.area_id,
    zone: (z.zone_class ?? z.zone) as Zone,
    suitability_score: z.suitability_future ?? z.suitability_score ?? 0,
    risk_index: z.nino_risk ?? z.risk_index ?? 0,
  }));
  const counts = Object.fromEntries(ZONES.map((k) => [k, items.filter((i: { zone: Zone }) => i.zone === k).length])) as Record<Zone, number>;
  return { future: r.future, counts, items };
};

// --- Alertas ---
export const alerts = (r: Raw): AlertsResponse => ({
  scenario: r.scenario, province: r.province ?? null, resumen: r.resumen ?? "",
  items: (r.items ?? []).map((i: Raw) => ({ ...i, provincia: provinceName(i.provincia), nivel: riskClassOf(i.perdida_pct), cantones: i.cantones ?? [] })),
  generated_by: r.generated_by === "ia" ? "ia" : "plantilla", model: r.model ?? null, provider: r.provider ?? null, disclaimer: r.disclaimer ?? "",
});
