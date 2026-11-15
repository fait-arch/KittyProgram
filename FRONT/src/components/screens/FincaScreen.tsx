"use client";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import type { FeatureCollection } from "geojson";
import * as api from "@/lib/api/endpoints";
import { useAreaDetail, useAreasGeojson, useLosses, useRequirements, useScenarios } from "@/lib/api/hooks";
import type { AreaClimate, ScenarioId } from "@/lib/api/types";
import { useChartTokens } from "@/lib/charts/tokens";
import { DEFAULT_SCENARIO, SCENARIO_IDS } from "@/lib/state/useMapState";
import { useTheme } from "@/lib/theme";
import { ringAreaHa, ringCentroid, selfIntersects, type LonLat } from "@/lib/geo/finca";
import { fmt1, fmtInt, fmtPct, fmtPctRange, fmtUsd } from "@/lib/design/format";
import { RISK_META } from "@/lib/design/colors";
import { Button, LinkButton } from "@/components/atoms/Button";
import { Icon } from "@/components/atoms/Icon";
import { Skeleton } from "@/components/atoms/Skeleton";
import { AlertLevelChip } from "@/components/molecules/AlertLevelChip";
import { KpiTile } from "@/components/molecules/KpiTile";
import { LossInterval } from "@/components/molecules/LossInterval";
import { ScenarioSelector } from "@/components/molecules/ScenarioSelector";
import { SaveOfflineButton } from "@/components/molecules/SaveOfflineButton";
import { RequirementCheck } from "@/components/organisms/RequirementCheck";

const FincaMap = dynamic(() => import("@/components/organisms/FincaMap"), { ssr: false, loading: () => <Skeleton className="absolute inset-0 rounded-none" /> });

const enc = (p: LonLat[]) => p.map(([x, y]) => `${x.toFixed(5)},${y.toFixed(5)}`).join(";");
const dec = (s: string | null): LonLat[] =>
  (s ?? "").split(";").map((t) => t.split(",").map(Number) as LonLat).filter((p) => p.length === 2 && p.every(Number.isFinite));

type SavedFinca = { name: string; points: LonLat[]; ha?: number; savedAt: string };
const KEY = "cr-fincas";
const readFincas = (): SavedFinca[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; } };

/**
 * Pantalla · Mi finca (Fase 3 del proyecto: «finca individual»).
 * Dibujar el lote o usar el GPS → hectáreas, cantón (/areas/lookup), pérdida estimada del cantón aplicada
 * a la finca y clima del punto (/point/climate, NASA POWER). Todo queda en la URL para compartirlo.
 */
export function FincaScreen() {
  const sp = useSearchParams();
  const router = useRouter();
  const { theme } = useTheme();
  const tok = useChartTokens();
  const points = useMemo(() => dec(sp.get("finca")), [sp]);
  const esc = sp.get("escenario") as ScenarioId;
  const scenario = SCENARIO_IDS.includes(esc) ? esc : DEFAULT_SCENARIO;
  const haInput = Number(sp.get("ha")) || 5;
  const [drawing, setDrawing] = useState(points.length === 0);
  const [gpsMsg, setGpsMsg] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedFinca[]>([]);
  const [coord, setCoord] = useState({ lat: "", lon: "" });
  useEffect(() => setSaved(readFincas()), []);

  const patch = useCallback((kv: Record<string, string | null>) => {
    const q = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(kv)) if (v == null || v === "") q.delete(k); else q.set(k, v);
    router.replace(`/finca?${q}`, { scroll: false });
  }, [sp, router]);
  const setPoints = (p: LonLat[]) => patch({ finca: p.length ? enc(p) : null });

  const isPoly = points.length >= 3;
  const crossing = isPoly && selfIntersects(points);
  const ha = isPoly ? ringAreaHa(points) : points.length === 1 ? haInput : 0;
  const center = isPoly ? ringCentroid(points) : points.length === 1 ? points[0] : null;
  const ready = !!center && (isPoly || points.length === 1) && !crossing;

  const look = useSWR(ready ? ["lookup", center![1].toFixed(4), center![0].toFixed(4)] : null, () => api.lookupPoint(center![1], center![0]), { revalidateOnFocus: false, shouldRetryOnError: false });
  const cantonId = look.data?.canton.id ?? null;
  const detail = useAreaDetail(cantonId, scenario);
  const clim = useSWR(ready ? ["pointclim", center![1].toFixed(2), center![0].toFixed(2)] : null, () => api.getPointClimate(center![1], center![0]), { revalidateOnFocus: false, shouldRetryOnError: false });
  const req = useRequirements();
  const { data: scenarios } = useScenarios();
  const { data: geo } = useAreasGeojson("canton");
  const { data: losses } = useLosses(scenario);
  const { data: context } = useSWR("geo/contexto", () => fetch("/geo/ecuador-contexto.geojson").then((r) => r.json() as Promise<FeatureCollection>), { revalidateOnFocus: false });
  const values = useMemo(() => new Map((losses?.items ?? []).map((i) => [i.area_id, i.loss_pct])), [losses]);
  const scLabel = scenarios?.find((s) => s.id === scenario)?.label ?? scenario;

  // Pérdida del cantón llevada a la finca: rendimiento y precio implícitos del cantón
  const d = detail.data;
  const farm = useMemo(() => {
    if (!d || !ha || !d.loss) return null;
    const l = d.loss;
    const yieldT = d.area.cacao_ha && l.loss_pct > 0 && l.loss_t ? l.loss_t / (d.area.cacao_ha * (l.loss_pct / 100)) : 0.54;
    const price = l.loss_t && l.loss_usd ? l.loss_usd / l.loss_t : 2700;
    const t = (p: number) => ha * yieldT * (p / 100);
    return { yieldT, price, t: t(l.loss_pct), tLo: t(l.loss_pct_low), tHi: t(l.loss_pct_high), usd: t(l.loss_pct) * price };
  }, [d, ha]);

  const pointClimate: AreaClimate | null = clim.data
    ? { temp_mean_c: clim.data.annual.t2m ?? NaN, rain_annual_mm: clim.data.annual.precip_mm ?? NaN, elevation_m: clim.data.elevation_m ?? NaN, soil_ph: null }
    : null;

  const gps = () => {
    if (!navigator.geolocation) { setGpsMsg("Este navegador no da la ubicación."); return; }
    setGpsMsg("Buscando ubicación…");
    navigator.geolocation.getCurrentPosition(
      (pos) => { setGpsMsg(`Ubicación con precisión de ±${Math.round(pos.coords.accuracy)} m.`); setDrawing(false); setPoints([[+pos.coords.longitude.toFixed(6), +pos.coords.latitude.toFixed(6)]]); },
      (e) => setGpsMsg(e.code === 1 ? "Permiso de ubicación denegado." : "No se pudo obtener la ubicación."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };
  const saveFinca = () => {
    const name = window.prompt("Nombre de la finca", look.data ? `Finca en ${look.data.canton.name}` : "Mi finca");
    if (!name) return;
    const list = [{ name, points, ha: points.length === 1 ? haInput : undefined, savedAt: new Date().toISOString() }, ...readFincas().filter((f) => f.name !== name)].slice(0, 20);
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* sin almacenamiento */ }
    setSaved(list);
  };

  return (
    <div className="flex h-full flex-col-reverse lg:flex-row">
      <aside className="flex min-h-0 w-full flex-col gap-5 overflow-y-auto border-outline-variant bg-surface p-5 lg:w-[440px] lg:shrink-0 lg:border-r lg:p-6">
        <header className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Mi finca</span>
          <h1 className="font-display text-[26px] leading-8 font-extrabold">¿Cuánto podría perder mi finca?</h1>
          <p className="text-sm text-on-surface-variant">Dibuje el lote en el mapa (un clic por esquina) o use su ubicación. Calculamos las hectáreas, el cantón y la pérdida estimada.</p>
        </header>

        <div className="flex flex-wrap gap-2">
          <Button variant={drawing ? "tonal" : "filled"} icon={drawing ? "check" : "polyline"} onClick={() => setDrawing((v) => !v)}>{drawing ? "Terminar dibujo" : points.length ? "Seguir dibujando" : "Dibujar lote"}</Button>
          <Button variant="outlined" icon="my_location" onClick={gps}>Mi ubicación</Button>
          <Button variant="text" icon="undo" onClick={() => setPoints(points.slice(0, -1))} disabled={!points.length}>Deshacer</Button>
          <Button variant="text" icon="delete" onClick={() => { setPoints([]); setDrawing(true); }} disabled={!points.length}>Borrar</Button>
        </div>
        {gpsMsg && <p className="-mt-3 text-xs text-on-surface-variant" aria-live="polite">{gpsMsg}</p>}
        {drawing && <p className="-mt-3 flex items-center gap-1.5 text-[13px] text-primary"><Icon name="touch_app" size={18} />Haga clic en el mapa para cada esquina del lote ({points.length} puestas). Arrastre un punto para moverlo.</p>}

        <details className="rounded-md border border-outline-variant p-3 text-sm">
          <summary className="cursor-pointer font-semibold">Escribir coordenadas (sin mapa)</summary>
          <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); const la = Number(coord.lat.replace(",", ".")), lo = Number(coord.lon.replace(",", ".")); if (Number.isFinite(la) && Number.isFinite(lo)) { setDrawing(false); setPoints([[lo, la]]); } }}>
            {(["lat", "lon"] as const).map((k) => (
              <label key={k} className="flex flex-col gap-1 text-xs text-on-surface-variant">{k === "lat" ? "Latitud" : "Longitud"}
                <input inputMode="decimal" required value={coord[k]} onChange={(e) => setCoord({ ...coord, [k]: e.target.value })} placeholder={k === "lat" ? "-1,55" : "-79,75"}
                  className="h-10 w-28 rounded-sm border border-outline bg-transparent px-2 text-sm text-on-surface" />
              </label>
            ))}
            <Button variant="tonal" icon="pin_drop" type="submit">Ubicar</Button>
          </form>
        </details>

        {points.length === 1 && (
          <label className="flex items-center gap-3 text-sm">Hectáreas de cacao
            <input type="number" min={0.1} step={0.1} value={haInput} onChange={(e) => patch({ ha: e.target.value })}
              className="h-10 w-24 rounded-sm border border-outline bg-transparent px-2 text-sm" />
          </label>
        )}

        <ScenarioSelector value={scenario} onChange={(s) => patch({ escenario: s })} scenarios={scenarios} />

        {crossing && <p className="flex gap-2 rounded-md bg-surface-container p-3 text-[13px]"><Icon name="warning" fill size={18} className="text-status-warn" />Los lados del lote se cruzan. Deshaga el último punto o mueva una esquina.</p>}

        {ready && (
          <section aria-label="Resultado de la finca" aria-busy={!d} className="flex flex-col gap-4 rounded-lg bg-surface-high p-5">
            <div className="flex flex-col">
              <span className="font-display text-[22px] font-extrabold leading-7">{fmt1(ha)} ha{look.data ? ` · ${look.data.canton.name}` : ""}</span>
              <span className="text-[13px] text-on-surface-variant">
                {look.data?.province?.name ?? ""}{look.data ? " · " : ""}{center![1].toFixed(4)}, {center![0].toFixed(4)}{isPoly ? ` · ${points.length} esquinas` : " · punto"}
              </span>
            </div>
            {look.error ? (
              <p className="text-sm text-error">El punto no cae en ningún cantón de la Costa con datos.</p>
            ) : !d || (!farm && d.loss) ? (
              <Skeleton className="h-40" />
            ) : !d.loss || !farm ? (
              <p className="text-sm text-on-surface-variant">El modelo todavía no tiene estimación de pérdida para {d.area.name} en este escenario.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-display text-[44px] font-black leading-[48px] tabular">{fmtPct(d.loss.loss_pct)}</span>
                  <AlertLevelChip risk={d.loss.risk_class} prefix="Pérdida" />
                </div>
                <p className="-mt-2 text-[13px] text-on-surface-variant">{RISK_META[d.loss.risk_class].alert} · {scLabel}</p>
                <LossInterval low={d.loss.loss_pct_low} mid={d.loss.loss_pct} high={d.loss.loss_pct_high} />
                <div className="grid grid-cols-2 gap-3">
                  <KpiTile value={`${fmt1(farm.t)} t`} label={`grano seco perdido en su finca (rango ${fmt1(farm.tLo)}–${fmt1(farm.tHi)} t)`} />
                  <KpiTile value={fmtUsd(farm.usd)} label="valor en riesgo" />
                </div>
                <p className="flex gap-2 rounded-md bg-surface-container p-3 text-[13px] leading-[18px]">
                  <Icon name="info" size={18} className="text-primary" />
                  <span>El modelo trabaja por cantón: se aplica el {fmtPct(d.loss.loss_pct)} de {d.area.name} a sus {fmt1(ha)} ha, con el rendimiento del cantón ({fmt1(farm.yieldT)} t/ha) y su precio (USD {fmtInt(farm.price)}/t). Rango probable {fmtPctRange(d.loss.loss_pct_low, d.loss.loss_pct_high)}.</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  <LinkButton variant="tonal" icon="map" href={`/?escenario=${scenario}&canton=${encodeURIComponent(d.area.id)}`}>Ver el cantón</LinkButton>
                  <LinkButton variant="outlined" icon="print" href={`/plantillas?tipo=ficha&canton=${encodeURIComponent(d.area.id)}&escenario=${scenario}`}>Ficha A4</LinkButton>
                  <Button variant="outlined" icon="bookmark_add" onClick={saveFinca}>Guardar finca</Button>
                  <SaveOfflineButton id={d.area.id} name={d.area.name} />
                </div>
              </>
            )}
          </section>
        )}

        {ready && req.data && (
          clim.data && pointClimate ? (
            <div className="flex flex-col gap-2">
              <RequirementCheck climate={pointClimate} req={req.data} />
              <p className="text-xs text-on-surface-muted">Clima del punto: {clim.data.source} · celda de ~{clim.data.resolution_km} km. {clim.data.warning}</p>
            </div>
          ) : clim.error ? (
            <p className="text-xs text-on-surface-muted">El clima del punto (NASA POWER) no está disponible ahora.</p>
          ) : <Skeleton className="h-32" />
        )}

        {saved.length > 0 && (
          <section aria-label="Fincas guardadas" className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Mis fincas (en este dispositivo)</span>
            <ul className="flex flex-wrap gap-2">
              {saved.map((f) => (
                <li key={f.name}>
                  <button type="button" onClick={() => { setDrawing(false); patch({ finca: enc(f.points), ha: f.ha ? String(f.ha) : null }); }}
                    className="state-layer inline-flex h-8 items-center gap-1.5 rounded-sm bg-secondary-container px-3 text-[13px] font-semibold text-on-secondary-container cursor-pointer">
                    <Icon name="agriculture" size={16} />{f.name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>
      <div className="relative min-h-[46vh] flex-1">
        <FincaMap areas={geo} context={context} values={values} points={points} onChange={setPoints} drawing={drawing} theme={theme}
          focusCanton={cantonId} accent={tok.primary} />
      </div>
    </div>
  );
}
