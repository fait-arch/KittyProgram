/**
 * Datos de DEMOSTRACIÓN (ilustrativos). Implementan el mismo contrato que FastAPI
 * para que el front funcione sin backend. No son resultados del modelo.
 * Fuente: public/mock/data.json y public/mock/cantones.geojson.
 */
import type {
  AreaDetail,
  AreaProps,
  PointClimate,
  PointLookup,
  AreaKind,
  AreaRef,
  AreasGeoJSON,
  CompareResponse,
  CropRequirements,
  EnsoCurrent,
  LossItem,
  LossSummary,
  LossesResponse,
  Meta,
  RiskClass,
  Scenario,
  ScenarioId,
  StrategiesResponse,
  Strategy,
  Suitability,
  Zone,
  ZonesResponse,
} from "./types";
import { riskClassOf } from "@/lib/design/colors";
import { pointInGeometry } from "@/lib/geo/finca";
import { ApiError } from "./client";

interface MockData {
  note: string;
  yield_t_ha: number;
  price_usd_t: number;
  areas: AreaRef[];
  losses: Record<ScenarioId, Record<string, number>>;
  zones: Record<string, Zone>;
}

let dataP: Promise<MockData> | null = null;
let geoP: Promise<AreasGeoJSON> | null = null;
const loadData = () => (dataP ??= fetch("/mock/data.json").then((r) => r.json() as Promise<MockData>));
const loadGeo = () => (geoP ??= fetch("/mock/cantones.geojson").then((r) => r.json() as Promise<AreasGeoJSON>));

/** Pseudoaleatorio estable por texto (FNV-1a) */
function h01(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0) / 0xffffffff;
}
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const r1 = (v: number) => Math.round(v * 10) / 10;
const DEMO = "Vinces";

export const MOCK_SCENARIOS: Scenario[] = [
  { id: "normal", label: "Año normal", group: "hoy", phase: 1, description: "Promedio de enero–junio en años neutros (2001–2025).", available: true, extrapolation: false },
  { id: "nino", label: "Año Niño", group: "hoy", phase: 1, description: "Promedio de enero–junio en años clasificados como El Niño.", available: true, extrapolation: false },
  { id: "actual", label: "Temporada actual", group: "hoy", phase: 1, description: "ENSO vigente (ONI y Niño 1+2 actuales) sobre el clima normal del área.", available: true, extrapolation: false },
  { id: "ssp245_2050", label: "2050 · SSP2-4.5", group: "2050", phase: 2, description: "Clima 2041–2060, emisiones moderadas (NEX-GDDP-CMIP6, método delta).", available: true, extrapolation: true },
  { id: "ssp585_2050", label: "2050 · SSP5-8.5", group: "2050", phase: 2, description: "Clima 2041–2060, emisiones altas (NEX-GDDP-CMIP6, método delta).", available: true, extrapolation: true },
];

export const mock = {
  async scenarios(): Promise<Scenario[]> {
    return MOCK_SCENARIOS;
  },

  async ensoCurrent(): Promise<EnsoCurrent> {
    // Valores del README del proyecto (NOAA CPC)
    return {
      phase: "nino",
      strength: "fuerte",
      oni: { value: 2.46, season: "ASO", year: 2026 },
      nino12: { anomaly_c: 5.25, month: "2026-10" },
      event_in_progress: true,
      source: "NOAA CPC",
      updated_at: "2026-11-01",
    };
  },

  async areas(kind: AreaKind = "canton", province?: string): Promise<AreaRef[]> {
    const d = await loadData();
    return d.areas.filter((a) => a.kind === kind && (!province || a.province === province));
  },

  async areasGeojson(_kind: AreaKind = "canton", province?: string): Promise<AreasGeoJSON> {
    const g = await loadGeo();
    if (!province) return g;
    return { ...g, features: g.features.filter((f) => f.properties.province === province) };
  },

  /** Demo de /areas/lookup: punto en polígono sobre los cantones de demostración */
  async lookupPoint(lat: number, lon: number): Promise<PointLookup> {
    const geo = await loadGeo();
    const f = geo.features.find((x) => pointInGeometry([lon, lat], x.geometry as { type: string; coordinates: unknown }));
    if (!f) throw new ApiError(404, "El punto no cae en ningún cantón de la Costa cargado");
    const p = f.properties as AreaProps;
    return { canton: { id: p.id, name: p.name }, province: { id: p.province.toLowerCase().replace(/\s+/g, "-"), name: p.province } };
  },

  /** Demo de /point/climate: el clima del cantón que contiene el punto (el real usa NASA POWER) */
  async pointClimate(lat: number, lon: number): Promise<PointClimate> {
    const hit = await mock.lookupPoint(lat, lon);
    const [det, req] = await Promise.all([mock.areaDetail(hit.canton.id, "normal"), mock.requirements()]);
    const c = det.climate;
    const val: Record<string, number | null> = { temp_mean: c.temp_mean_c, rain_annual: c.rain_annual_mm, elevation: c.elevation_m, soil_ph: c.soil_ph };
    return {
      point: { lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100 },
      elevation_m: c.elevation_m,
      source: "Demostración (clima del cantón)",
      resolution_km: 55,
      annual: { t2m: c.temp_mean_c, rh2m: null, precip_mm: c.rain_annual_mm },
      requirement_check: req.parameters.map((p) => {
        const v = val[p.id];
        const ok = v != null && (p.optimal_min == null || v >= p.optimal_min) && (p.optimal_max == null || v <= p.optimal_max);
        const out = v != null && ((p.absolute_min != null && v < p.absolute_min) || (p.absolute_max != null && v > p.absolute_max));
        return { parameter: p.id, label: p.label, value: v, unit: p.unit, opt: [p.optimal_min, p.optimal_max], abs: [p.absolute_min, p.absolute_max],
          status: v == null ? "sin_dato" : ok ? "ok" : out ? "out" : "warn" };
      }),
      warning: "Datos de demostración.",
    };
  },

  async requirements(): Promise<CropRequirements> {
    return {
      crop: "cacao",
      source: "ECOCROP (OpenCLIM/ecocrop)",
      parameters: [
        { id: "temp_mean", label: "Temperatura media", unit: "°C", optimal_min: 21, optimal_max: 32, absolute_min: 10, absolute_max: 38 },
        { id: "rain_annual", label: "Lluvia anual", unit: "mm", optimal_min: 1200, optimal_max: 3000, absolute_min: 900, absolute_max: 7600 },
        { id: "elevation", label: "Altitud", unit: "m", optimal_min: 0, optimal_max: 900, absolute_min: null, absolute_max: null },
        { id: "soil_ph", label: "pH del suelo", unit: "", optimal_min: 5.0, optimal_max: 6.5, absolute_min: null, absolute_max: null },
      ],
    };
  },

  async losses(scenario: ScenarioId, kind: AreaKind = "canton", province?: string): Promise<LossesResponse> {
    const d = await loadData();
    const items = d.areas
      .filter((a) => !province || a.province === province)
      .map((a) => lossItem(d, a, scenario));
    return { scenario, kind, model: "demo (ilustrativo)", items };
  },

  async lossSummary(scenario: ScenarioId, province?: string): Promise<LossSummary> {
    const d = await loadData();
    const areas = d.areas.filter((a) => !province || a.province === province);
    const sum = (sc: ScenarioId) =>
      areas.reduce(
        (acc, a) => {
          const it = lossItem(d, a, sc);
          acc.t += it.loss_t ?? 0;
          acc.usd += it.loss_usd ?? 0;
          return acc;
        },
        { t: 0, usd: 0 },
      );
    const cur = sum(scenario);
    const nor = sum("normal");
    const byClass = { baja: 0, moderada: 0, alta: 0, muy_alta: 0, critica: 0 } as Record<RiskClass, number>;
    areas.forEach((a) => byClass[riskClassOf((d.losses[scenario] ?? d.losses.nino)[a.id])]++);
    return {
      scenario,
      province: province ?? null,
      loss_t: cur.t,
      loss_usd: cur.usd,
      vs_normal: scenario === "normal" ? null : { loss_t: cur.t - nor.t, loss_usd: cur.usd - nor.usd },
      n_areas: areas.length,
      areas_by_class: byClass,
    };
  },

  async areaDetail(id: string, scenario: ScenarioId): Promise<AreaDetail> {
    const d = await loadData();
    const a = findArea(d, id);
    const it = lossItem(d, a, scenario);
    const pct = it.loss_pct;
    const nor = d.losses.normal[a.id];
    const isDemo = a.name === DEMO;
    const f = clamp(Math.sqrt(pct / 22.4), 0.3, 1.25);
    const MONI = [0.71, 0.78, 0.82, 0.74, 0.58, 0.41, 0.22, 0.15, 0.14, 0.18, 0.27, 0.45];
    const PHYT = [0.55, 0.62, 0.7, 0.61, 0.42, 0.28, 0.14, 0.09, 0.08, 0.1, 0.17, 0.33];
    const rain = isDemo ? 3400 : Math.round((1800 + pct * 55 + h01(a.id + "rain") * 400) / 10) * 10;
    const climate = {
      temp_mean_c: isDemo ? 26 : r1(24.6 + h01(a.id + "t") * 2.6),
      rain_annual_mm: rain,
      elevation_m: isDemo ? 15 : Math.round(a.province === "Santo Domingo" ? 300 + h01(a.id) * 300 : 5 + h01(a.id + "z") * 180),
      soil_ph: isDemo ? 6.1 : r1(5.4 + h01(a.id + "ph") * 1.3),
    };
    return {
      area: a,
      scenario,
      loss: {
        ...it,
        vs_normal: scenario === "normal" ? null : { loss_pct: nor, delta_pct: r1(pct - nor), delta_usd: (it.loss_usd ?? 0) - lossItem(d, a, "normal").loss_usd! },
      },
      top_factors: [
        { feature: "fav_days_monilia", label: "Días húmedos y templados, favorables a la moniliasis", value: Math.round(60 + pct * 2.6), unit: "días (ene–jun)", contribution_pct: r1(pct * 0.44), source: "ERA5-Land" },
        { feature: "heavy_rain_days", label: "Días de lluvia muy fuerte (más de 50 mm)", value: Math.round(4 + pct * 0.45), unit: "días", contribution_pct: r1(pct * 0.23), source: "NASA GPM IMERG" },
        { feature: "saturated_days", label: "Días con el suelo encharcado", value: Math.round(5 + pct * 0.7), unit: "días", contribution_pct: r1(pct * 0.093), source: "NASA SMAP" },
      ],
      monthly_risk: MONI.map((m, i) => ({ month: i + 1, monilia: clamp(m * f, 0, 0.98), phytophthora: clamp(PHYT[i] * f, 0, 0.98) })),
      suitability: suitability(a, scenario, rain),
      climate,
      model: { name: "cacao_loss_v1 (demo)", mae: 6.3, trained_years: [2002, 2024] },
      disclaimer: "Estimación con datos satelitales y estadísticos. Validar con técnicos del INIAP/MAG.",
    };
  },

  async strategies(id: string, scenario: ScenarioId): Promise<StrategiesResponse> {
    const d = await loadData();
    const a = findArea(d, id);
    const it = lossItem(d, a, scenario);
    const items: Strategy[] = [
      {
        id: "sanitario", rank: 1, name: "Manejo sanitario",
        summary: "Cosecha sanitaria semanal, poda y retiro de mazorcas enfermas",
        expected_loss_pct: r1(it.loss_pct * 0.63), avoided_loss_t: (it.loss_t ?? 0) * 0.37, avoided_loss_usd: (it.loss_usd ?? 0) * 0.37, protects_income: false,
        why: "La moniliasis se dispersa con días húmedos sostenidos. Retirar cada semana las mazorcas enfermas corta el ciclo de esporas en los meses de mayor riesgo (enero a abril).",
        evidence: "Práctica recomendada para moniliasis en cacao. El efecto en este cantón es una estimación del modelo y debe validarse con INIAP.",
        data_gaps: "Incidencia real de moniliasis en fincas del cantón para calibrar el efecto.",
        risks: "Requiere mano de obra cada semana en plena temporada de lluvias.",
      },
      {
        id: "drenaje_sombra", rank: 2, name: "Drenaje + sombra regulada",
        summary: "Agroforestería: menos encharcamiento y estrés térmico",
        expected_loss_pct: r1(it.loss_pct * 0.82), avoided_loss_t: (it.loss_t ?? 0) * 0.18, avoided_loss_usd: (it.loss_usd ?? 0) * 0.18, protects_income: false,
        why: "El suelo encharcado y el exceso de lluvia favorecen la mazorca negra y ahogan las raíces. Drenar y regular la sombra baja la humedad dentro del cacaotal.",
        evidence: "Indicado en zonas bajas con suelo saturado (SMAP) y relieve plano (SRTM). Efecto estimado por el modelo.",
        data_gaps: "Mapa de drenaje de las fincas y tipo de suelo.",
        risks: "Inversión inicial; demasiada sombra reduce la floración.",
      },
      {
        id: "diversificacion", rank: 3, name: "Diversificación",
        summary: "Cacao + plátano o maderables; intercalados en cacao joven",
        expected_loss_pct: it.loss_pct, avoided_loss_t: null, avoided_loss_usd: null, protects_income: true,
        why: "No reduce la enfermedad, pero reparte el riesgo: si el cacao pierde, la finca mantiene otros ingresos.",
        evidence: "Estrategia de adaptación de largo plazo, útil en zonas de manejo o transición.",
        data_gaps: "Precios y mercado local de los cultivos asociados.",
        risks: "Competencia por luz y nutrientes si no se planifica el arreglo.",
      },
    ];
    return { area_id: a.id, scenario, baseline_loss_pct: it.loss_pct, items };
  },

  async compare(id: string, scenarios: ScenarioId[]): Promise<CompareResponse> {
    const d = await loadData();
    const a = findArea(d, id);
    return {
      area: a,
      items: scenarios.map((sc) => ({
        scenario: sc,
        loss: lossItem(d, a, sc),
        suitability: suitability(a, sc, a.name === DEMO ? 3400 : 2400),
        extrapolation: sc.endsWith("_2050"),
      })),
    };
  },

  async zones(future: ScenarioId): Promise<ZonesResponse> {
    const d = await loadData();
    const counts: Record<Zone, number> = { segura: 0, manejo: 0, transicion: 0, critica: 0 };
    const items = d.areas.map((a) => {
      const base = d.zones[a.id];
      const aptLow = base === "transicion" || base === "critica";
      const riskHigh = (d.losses[future] ?? d.losses.ssp245_2050)[a.id] >= 22;
      const zone: Zone = aptLow ? (riskHigh ? "critica" : "transicion") : riskHigh ? "manejo" : "segura";
      counts[zone]++;
      return { area_id: a.id, zone, suitability_score: aptLow ? 0.45 : 0.78, risk_index: clamp((d.losses[future] ?? d.losses.ssp245_2050)[a.id] / 50, 0, 1) };
    });
    return { future, counts, items };
  },

  async meta(): Promise<Meta> {
    return {
      sources: [
        { id: "gpm", name: "GPM IMERG", provider: "NASA", use: "Lluvia diaria y días de lluvia fuerte" },
        { id: "smap", name: "SMAP", provider: "NASA", use: "Humedad del suelo (días encharcados)" },
        { id: "modis", name: "MODIS NDVI", provider: "NASA", use: "Vigor del cacaotal" },
        { id: "srtm", name: "SRTM", provider: "NASA", use: "Altitud y zonas bajas" },
        { id: "cmip6", name: "NEX-GDDP-CMIP6", provider: "NASA", use: "Clima 2041–2060 (SSP2-4.5 y SSP5-8.5)" },
        { id: "era5", name: "ERA5-Land", provider: "Copernicus", use: "Temperatura y humedad relativa (moniliasis)" },
        { id: "enso", name: "ONI y Niño 1+2", provider: "NOAA CPC", use: "Fase e intensidad de El Niño" },
        { id: "espac", name: "ESPAC", provider: "INEC", use: "Producción y superficie de cacao" },
        { id: "ecocrop", name: "ECOCROP", provider: "FAO", use: "Requerimientos del cacao" },
      ],
      model: { name: "cacao_loss_v1 (demo)", mae: 6.3, skill_vs_baseline: 0.21, interval_coverage: 0.8, trained_years: [2002, 2024] },
      updated_at: "2026-11-14",
    };
  },
};

function findArea(d: MockData, id: string): AreaRef {
  const a = d.areas.find((x) => x.id === id);
  if (!a) throw new Error(`Área no encontrada: ${id}`);
  return a;
}

function lossItem(d: MockData, a: AreaRef, scenario: ScenarioId): LossItem {
  const pct = (d.losses[scenario] ?? d.losses.nino)[a.id];
  const t = (a.cacao_ha ?? 0) * d.yield_t_ha * (pct / 100);
  return {
    area_id: a.id,
    loss_pct: pct,
    loss_pct_low: r1(pct * 0.55),
    loss_pct_high: r1(Math.min(100, pct * 1.55)),
    loss_t: t,
    loss_usd: t * d.price_usd_t,
    risk_class: riskClassOf(pct),
  };
}

function suitability(a: AreaRef, scenario: ScenarioId, rain: number): Suitability {
  const BASE: Record<ScenarioId, number> = { normal: 0.86, nino: 0.82, nino_extremo: 0.74, nina: 0.85, actual: 0.8, ssp245_2050: 0.71, ssp585_2050: 0.58 };
  const score = a.name === DEMO ? BASE[scenario] : clamp(BASE[scenario] + (h01(a.id + "apt") - 0.5) * 0.16, 0.2, 0.95);
  return {
    score: Math.round(score * 100) / 100,
    class: score >= 0.7 ? "apta" : score >= 0.5 ? "marginal" : "no_apta",
    limiting_factors: rain > 3000 ? ["rain_annual"] : [],
  };
}
