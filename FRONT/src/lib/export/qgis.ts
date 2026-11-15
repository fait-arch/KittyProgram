/**
 * Exportación en el navegador (modo demostración o sin backend):
 * GeoJSON + estilo .qml con el MISMO nombre de archivo (QGIS lo aplica al abrir la capa),
 * SLD 1.1 y CSV, con los datos que entrega la API (o los de demostración si no hay backend).
 */
import { isUsingMock } from "@/lib/api/client";
import type { AreasGeoJSON, LossesResponse, ScenarioId, ZonesResponse } from "@/lib/api/types";

const FUENTE_DEMO = "DATOS DE DEMOSTRACION - no son resultados del modelo";
/** Rótulo de la columna «fuente»: demostración o el modelo que respondió en el backend */
const fuente = (model?: string) => (isUsingMock() ? FUENTE_DEMO : `CacaoResiliente API${model ? ` - modelo ${model}` : ""}`);

export const LAYER_NAME: Record<ScenarioId, string> = {
  normal: "perdida_normal",
  nino: "perdida_nino",
  nino_extremo: "perdida_nino_extremo",
  nina: "perdida_nina",
  actual: "perdida_actual",
  ssp245_2050: "perdida_ssp245_2050",
  ssp585_2050: "perdida_ssp585_2050",
};

export function saveBlob(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

async function saveStyle(style: "perdida_cacao" | "zonas_2050", ext: "qml" | "sld", filename: string) {
  const res = await fetch(`/qgis/${style}.${ext}`);
  saveBlob(new Blob([await res.text()], { type: "application/xml" }), filename);
}

/** Campos de ≤ 10 caracteres: también sirven al guardar como Shapefile en QGIS. */
export function lossFeatureCollection(areas: AreasGeoJSON, losses: LossesResponse, zones?: ZonesResponse, src = fuente(losses.model)) {
  const byId = new Map(losses.items.map((i) => [i.area_id, i]));
  const zoneById = new Map(zones?.items.map((z) => [z.area_id, z.zone]) ?? []);
  return {
    type: "FeatureCollection" as const,
    name: LAYER_NAME[losses.scenario],
    crs: { type: "name", properties: { name: "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    features: areas.features
      .filter((f) => byId.has(f.properties.id))
      .map((f) => {
        const l = byId.get(f.properties.id)!;
        return {
          type: "Feature" as const,
          geometry: f.geometry,
          properties: {
            canton: f.properties.name,
            provincia: f.properties.province,
            escenario: losses.scenario,
            loss_pct: l.loss_pct,
            loss_p10: l.loss_pct_low,
            loss_p90: l.loss_pct_high,
            clase: l.risk_class,
            zona_2050: zoneById.get(f.properties.id) ?? null,
            fuente: src,
          },
        };
      }),
  };
}

export async function downloadLossLayer(areas: AreasGeoJSON, losses: LossesResponse, zones?: ZonesResponse) {
  const name = LAYER_NAME[losses.scenario];
  const fc = lossFeatureCollection(areas, losses, zones);
  saveBlob(new Blob([JSON.stringify(fc)], { type: "application/geo+json" }), `${name}.geojson`);
  await saveStyle("perdida_cacao", "qml", `${name}.qml`);
}

export async function downloadZonesLayer(areas: AreasGeoJSON, zones: ZonesResponse) {
  const byId = new Map(zones.items.map((z) => [z.area_id, z]));
  const fc = {
    type: "FeatureCollection",
    name: "zonas_2050",
    features: areas.features
      .filter((f) => byId.has(f.properties.id))
      .map((f) => ({
        type: "Feature",
        geometry: f.geometry,
        properties: { canton: f.properties.name, provincia: f.properties.province, zona_2050: byId.get(f.properties.id)!.zone, escenario: zones.future, fuente: fuente() },
      })),
  };
  saveBlob(new Blob([JSON.stringify(fc)], { type: "application/geo+json" }), "zonas_2050.geojson");
  await saveStyle("zonas_2050", "qml", "zonas_2050.qml");
}

export const downloadSld = (zones: boolean) =>
  zones ? saveStyle("zonas_2050", "sld", "zonas_2050.sld") : saveStyle("perdida_cacao", "sld", "perdida_cacao.sld");

export function downloadCsv(areas: AreasGeoJSON, list: LossesResponse[]) {
  const names = new Map(areas.features.map((f) => [f.properties.id, f.properties]));
  const rows = [["canton", "provincia", "escenario", "loss_pct", "loss_p10", "loss_p90", "clase", "loss_t", "loss_usd"].join(",")];
  for (const l of list) {
    for (const i of l.items) {
      const a = names.get(i.area_id);
      rows.push([a?.name, a?.province, l.scenario, i.loss_pct, i.loss_pct_low, i.loss_pct_high, i.risk_class, Math.round(i.loss_t ?? 0), Math.round(i.loss_usd ?? 0)]
        .map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","));
    }
  }
  saveBlob(new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" }), "cacaoresiliente_perdidas.csv");
}
