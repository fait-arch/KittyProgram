"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAreas, useScenarios } from "@/lib/api/hooks";
import { useDataSource } from "@/lib/api/client";
import type { ScenarioId } from "@/lib/api/types";
import { DEFAULT_SCENARIO, SCENARIO_IDS } from "@/lib/state/useMapState";
import { downloadNodePng } from "@/lib/export/png";
import { Button } from "@/components/atoms/Button";
import { Icon } from "@/components/atoms/Icon";
import { SegmentedButton } from "@/components/molecules/SegmentedButton";
import { ShareCard } from "@/components/templates/plantillas/ShareCard";
import { FichaA4 } from "@/components/templates/plantillas/FichaA4";
import { VideoCover } from "@/components/templates/plantillas/VideoCover";

type Tipo = "tarjeta" | "ficha" | "portada";
const SIZE: Record<Tipo, [number, number, string]> = {
  tarjeta: [1080, 1080, "Tarjeta para compartir · 1080 × 1080"],
  ficha: [794, 1123, "Ficha A4 para el técnico · imprimir o guardar como PDF"],
  portada: [1920, 1080, "Portada del video / presentación · 1920 × 1080"],
};

/** Pantalla · plantillas listas para compartir, imprimir o grabar (fase 3). Estado en la URL. */
export function TemplatesScreen() {
  const sp = useSearchParams();
  const router = useRouter();
  const tipo = (["tarjeta", "ficha", "portada"].includes(sp.get("tipo") ?? "") ? sp.get("tipo") : "tarjeta") as Tipo;
  const canton = sp.get("canton") ?? "los-rios-vinces";
  const esc = sp.get("escenario") as ScenarioId;
  const scenario = SCENARIO_IDS.includes(esc) ? esc : DEFAULT_SCENARIO;
  const set = (k: string, v: string) => { const q = new URLSearchParams(sp.toString()); q.set(k, v); router.replace(`/plantillas?${q}`, { scroll: false }); };
  const { data: areas } = useAreas("canton");
  const { data: scenarios } = useScenarios();
  const { mock } = useDataSource();
  const node = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.5);
  const [busy, setBusy] = useState(false);
  const [w, h, desc] = SIZE[tipo];

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setScale(Math.min(1, (e.contentRect.width - 2) / w)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, [w]);

  const download = async () => {
    if (!node.current) return;
    setBusy(true);
    try {
      await downloadNodePng(node.current, `cacaoresiliente-${tipo}-${canton}-${scenario}.png`, tipo === "portada" ? 1 : 1);
    } finally { setBusy(false); }
  };
  const props = { canton, scenario, demo: mock };

  return (
    <div className="min-h-dvh bg-surface-lowest">
      <div className="no-print sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-outline-variant bg-surface px-4 py-3 lg:px-8">
        <Link href={`/?escenario=${scenario}&canton=${encodeURIComponent(canton)}`} className="state-layer grid size-10 place-items-center rounded-full" aria-label="Volver al mapa"><Icon name="arrow_back" /></Link>
        <div className="mr-auto">
          <h1 className="font-display text-xl font-bold leading-7">Plantillas</h1>
          <p className="text-xs text-on-surface-variant">{desc}</p>
        </div>
        <SegmentedButton label="Plantilla" value={tipo} onChange={(v) => set("tipo", v)} className="w-[360px]"
          options={[{ value: "tarjeta", label: "Tarjeta" }, { value: "ficha", label: "Ficha A4" }, { value: "portada", label: "Portada" }]} />
        <label className="flex h-10 items-center gap-2 rounded-sm border border-outline px-3 text-sm">
          <span className="sr-only">Cantón</span>
          <select value={canton} onChange={(e) => set("canton", e.target.value)} className="bg-transparent font-semibold outline-none">
            {(areas ?? []).map((a) => <option key={a.id} value={a.id}>{a.name} · {a.province}</option>)}
          </select>
        </label>
        <label className="flex h-10 items-center gap-2 rounded-sm border border-outline px-3 text-sm">
          <span className="sr-only">Escenario</span>
          <select value={scenario} onChange={(e) => set("escenario", e.target.value)} className="bg-transparent font-semibold outline-none">
            {SCENARIO_IDS.map((id) => <option key={id} value={id}>{scenarios?.find((s) => s.id === id)?.label ?? id}</option>)}
          </select>
        </label>
        {tipo === "ficha"
          ? <Button variant="filled" icon="print" onClick={() => window.print()}>Imprimir / PDF</Button>
          : <Button variant="filled" icon={busy ? "hourglass_top" : "download"} onClick={download} disabled={busy}>{busy ? "Generando…" : "Descargar PNG"}</Button>}
      </div>
      <div ref={box} className="mx-auto max-w-[1400px] p-4 lg:p-8 print:max-w-none print:p-0">
        <div className="print:!h-auto" style={{ height: h * scale }}>
          <div className="print-area origin-top-left shadow-2xl" style={{ transform: `scale(${scale})`, width: w }}>
            {tipo === "tarjeta" && <ShareCard ref={node} {...props} />}
            {tipo === "ficha" && <FichaA4 ref={node} {...props} />}
            {tipo === "portada" && <VideoCover ref={node} {...props} />}
          </div>
        </div>
      </div>
    </div>
  );
}
