"use client";
import { useState } from "react";
import * as api from "@/lib/api/endpoints";
import { useDataSource } from "@/lib/api/client";
import type { ExportFormat, ScenarioId } from "@/lib/api/types";
import { RISK_CLASSES, RISK_LABEL, RISK_RANGE, type LossLevel } from "@/lib/design/colors";
import { downloadCsv, downloadLossLayer, downloadSld, downloadZonesLayer, LAYER_NAME } from "@/lib/export/qgis";
import { cn } from "@/lib/cn";
import { Dialog } from "@/components/molecules/Dialog";
import { Button } from "@/components/atoms/Button";
import { FilterChip } from "@/components/atoms/FilterChip";
import { Icon } from "@/components/atoms/Icon";
import { Badge } from "@/components/atoms/Badge";
import { Swatch } from "@/components/atoms/Swatch";

type Tab = "qgis" | "pdf" | "csv";
const LAYERS: { id: ScenarioId | "zonas"; label: string }[] = [
  { id: "normal", label: "Año normal" },
  { id: "nino", label: "Año Niño" },
  { id: "actual", label: "Temporada actual" },
  { id: "ssp245_2050", label: "2050 · SSP2-4.5" },
  { id: "ssp585_2050", label: "2050 · SSP5-8.5" },
  { id: "zonas", label: "Matriz de zonas 2050" },
];
const FORMATS: { id: ExportFormat; name: string; desc: string; backend: boolean }[] = [
  { id: "gpkg", name: "GeoPackage (.gpkg) con estilo", desc: "Un archivo con todas las capas. QGIS lo abre con la leyenda lista (estilo en layer_styles).", backend: true },
  { id: "geojson", name: "GeoJSON + estilo .qml", desc: "Mismo nombre de archivo: QGIS aplica el estilo al abrir la capa.", backend: false },
  { id: "shp", name: "Shapefile (.zip) + .qml", desc: "Para programas SIG antiguos. Campos de ≤ 10 caracteres.", backend: true },
  { id: "sld", name: "Solo estilo SLD 1.1", desc: "Para GeoServer u otros SIG que leen Styled Layer Descriptor.", backend: false },
];
const FIELDS = [
  ["canton", "texto", "Nombre del cantón"],
  ["provincia", "texto", "Provincia"],
  ["escenario", "texto", "normal · nino · actual · ssp245_2050 · ssp585_2050"],
  ["loss_pct", "real", "Pérdida estimada (%) — campo de la simbología"],
  ["loss_p10", "real", "Rango bajo (p10)"],
  ["loss_p90", "real", "Rango alto (p90)"],
  ["clase", "texto", "baja · moderada · alta · muy_alta · critica"],
  ["zona_2050", "texto", "segura · manejo · transicion · critica"],
  ["fuente", "texto", "Modelo, versión y fecha"],
];

/** Diálogo "Exportar": capa para QGIS, mapa en PDF y tabla CSV. */
export function ExportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { mock } = useDataSource();
  const [tab, setTab] = useState<Tab>("qgis");
  const [sel, setSel] = useState<Record<string, boolean>>({ normal: true, nino: true, actual: true });
  const [format, setFormat] = useState<ExportFormat>("gpkg");
  const [crs, setCrs] = useState<4326 | 32717>(4326);
  const [level, setLevel] = useState<"canton" | "province">("canton");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const scenarios = LAYERS.filter((l) => l.id !== "zonas" && sel[l.id]).map((l) => l.id as ScenarioId);
  const withZones = !!sel.zonas;
  const nLayers = scenarios.length + (withZones ? 1 : 0);
  const browserOnly = mock; // sin backend: se arma en el navegador
  const effectiveFormat: ExportFormat = browserOnly && FORMATS.find((f) => f.id === format)?.backend ? "geojson" : format;

  async function run() {
    setBusy(true);
    setMsg(null);
    try {
      if (tab === "pdf") {
        onClose();
        setTimeout(() => window.print(), 300);
        return;
      }
      if (tab === "csv") {
        const [areas, ...list] = await Promise.all([api.getAreasGeojson("canton"), ...scenarios.map((s) => api.getLosses(s))]);
        downloadCsv(areas, list);
        return;
      }
      if (effectiveFormat === "sld") {
        await downloadSld(false);
        if (withZones) await downloadSld(true);
        return;
      }
      if (!browserOnly) {
        window.location.href = api.exportUrl({ scenarios, format: effectiveFormat, crs, level, zones: withZones });
        return;
      }
      const areas = await api.getAreasGeojson("canton");
      const zones = await api.getZones("ssp245_2050");
      for (const s of scenarios) await downloadLossLayer(areas, await api.getLosses(s), zones);
      if (withZones) await downloadZonesLayer(areas, zones);
      setMsg(`Descargados ${nLayers * 2} archivos (.geojson + .qml). Arrástralos juntos a QGIS.`);
    } catch (e) {
      setMsg(`No se pudo exportar: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  const cta =
    tab === "pdf" ? "Imprimir / guardar PDF" : tab === "csv" ? "Descargar .csv" :
    effectiveFormat === "gpkg" ? "Descargar .gpkg" : effectiveFormat === "shp" ? "Descargar .zip (SHP + QML)" :
    effectiveFormat === "sld" ? "Descargar .sld" : browserOnly ? "Descargar .geojson + .qml" : "Descargar .zip (GeoJSON + QML)";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Exportar"
      icon="map"
      footer={
        <>
          <Icon name="info" size={20} className="text-primary" />
          <span className="min-w-[200px] flex-1 text-[13px] leading-[18px] text-on-surface-variant">
            {msg ?? `${nLayers} ${nLayers === 1 ? "capa" : "capas"} · cifras estimadas: cada archivo incluye el campo «fuente». Validar con INIAP/MAG.`}
          </span>
          <Button variant="text" onClick={onClose}>Cancelar</Button>
          <Button variant="filled" icon="download" onClick={run} disabled={busy || (tab !== "pdf" && nLayers === 0 && effectiveFormat !== "sld")}>
            {busy ? "Preparando…" : cta}
          </Button>
        </>
      }
    >
      <div role="tablist" aria-label="Tipo de exportación" className="mb-5 flex border-b border-outline-variant">
        {([["qgis", "layers", "Capa para QGIS"], ["pdf", "picture_as_pdf", "Mapa en PDF"], ["csv", "table_view", "Tabla CSV"]] as const).map(([k, ic, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn("flex h-12 items-center gap-2 px-5 text-sm cursor-pointer", tab === k ? "border-b-[3px] border-primary font-bold text-on-surface" : "font-semibold text-on-surface-variant")}>
            <Icon name={ic} size={20} />
            {l}
          </button>
        ))}
      </div>

      {tab === "pdf" ? (
        <p className="max-w-prose text-sm leading-6 text-on-surface-variant">
          Imprime la vista actual del mapa con su leyenda, escala, norte y fuentes. En el diálogo del navegador elige
          «Guardar como PDF». Para láminas con composición completa, exporta la capa para QGIS.
        </p>
      ) : (
        <div className="grid gap-6 md:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Capas (una por escenario)</span>
              <div className="flex flex-wrap gap-2">
                {LAYERS.filter((l) => tab === "qgis" || l.id !== "zonas").map((l) => (
                  <FilterChip key={l.id} selected={!!sel[l.id]} onClick={() => setSel((s) => ({ ...s, [l.id]: !s[l.id] }))}>{l.label}</FilterChip>
                ))}
              </div>
            </div>
            {tab === "qgis" && (
              <>
                <div role="radiogroup" aria-label="Formato" className="flex flex-col gap-1">
                  <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Formato</span>
                  {FORMATS.map((f) => {
                    const disabled = browserOnly && f.backend;
                    const on = effectiveFormat === f.id;
                    return (
                      <button key={f.id} type="button" role="radio" aria-checked={on} disabled={disabled} onClick={() => setFormat(f.id)}
                        className={cn("flex w-full items-start gap-3 rounded-md p-2.5 text-left cursor-pointer disabled:cursor-not-allowed disabled:opacity-45", on && "bg-surface-highest")}>
                        <Icon name={on ? "radio_button_checked" : "radio_button_unchecked"} fill size={22} className={on ? "text-primary" : "text-on-surface-muted"} />
                        <span className="flex flex-1 flex-col">
                          <span className="flex items-center gap-2 text-[15px] font-bold">
                            {f.name}
                            {f.id === "gpkg" && <Badge>RECOMENDADO</Badge>}
                          </span>
                          <span className="text-[13px] leading-[18px] text-on-surface-variant">{disabled ? "Requiere el backend (GET /api/v1/export)." : f.desc}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-0.5 rounded-sm border border-outline px-3.5 py-2">
                    <span className="text-xs text-on-surface-variant">Sistema de referencia (SRC)</span>
                    <select value={crs} onChange={(e) => setCrs(Number(e.target.value) as 4326 | 32717)} className="bg-transparent text-[15px] font-semibold outline-none">
                      <option value={4326}>EPSG:4326 · WGS 84 (grados)</option>
                      <option value={32717} disabled={browserOnly}>EPSG:32717 · UTM 17S (metros)</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-0.5 rounded-sm border border-outline px-3.5 py-2">
                    <span className="text-xs text-on-surface-variant">Nivel</span>
                    <select value={level} onChange={(e) => setLevel(e.target.value as "canton" | "province")} className="bg-transparent text-[15px] font-semibold outline-none">
                      <option value="canton">Cantón</option>
                      <option value="province" disabled={browserOnly}>Provincia</option>
                    </select>
                  </label>
                </div>
              </>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-3.5">
            <div className="flex flex-col gap-2 rounded-lg border border-outline-variant bg-surface-low p-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Así se verá la leyenda en QGIS</span>
              <div className="flex flex-col gap-1 rounded-sm bg-[#FAF7EF] px-3 py-2.5 text-[13px] text-[#14261C]">
                <span className="flex items-center gap-1.5 font-bold"><Icon name="check_box" fill size={16} className="text-[#0A6D37]" />{LAYER_NAME[scenarios[0] ?? "nino"]}</span>
                {RISK_CLASSES.map((c, i) => (
                  <span key={c} className="flex items-center gap-2 pl-6">
                    <Swatch level={i as LossLevel} size="sm" className="!w-4 !rounded-none" />
                    {RISK_RANGE[i]} % · {RISK_LABEL[c]}
                  </span>
                ))}
              </div>
              <span className="text-xs text-on-surface-variant">Graduado sobre <code className="font-mono text-on-surface">loss_pct</code> · alerta de 5 niveles (IPC / SNGR) · Crítica con rayado · borde 0,26 mm</span>
            </div>
            <div className="flex flex-col gap-1.5 rounded-lg border border-outline-variant bg-surface-low p-4">
              <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Campos</span>
              {FIELDS.map(([n, t, d]) => (
                <div key={n} className="grid grid-cols-[88px_56px_minmax(0,1fr)] gap-2 text-xs leading-[18px]">
                  <code className="font-mono">{n}</code>
                  <span className="text-on-surface-muted">{t}</span>
                  <span className="truncate text-on-surface-variant" title={d}>{d}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}
