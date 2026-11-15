"use client";
/**
 * Estado de la pantalla en la URL (?escenario=nino&canton=<id del cantón>&provincia=…&capa=zonas)
 * para poder compartir un enlace exacto y volver atrás con el navegador.
 */
import { useCallback, useEffect, useMemo } from "react";
import { useAreas } from "@/lib/api/hooks";
import { DATA_MODE } from "@/lib/api/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ScenarioId } from "@/lib/api/types";

export const SCENARIO_IDS: ScenarioId[] = ["normal", "nino", "nino_extremo", "nina", "actual", "ssp245_2050", "ssp585_2050"];
// Ecuador está hoy con El Niño: por defecto se abre la temporada en curso (no el promedio de años Niño 2001–2025)
export const DEFAULT_SCENARIO: ScenarioId = "actual";
export type MapLayer = "perdida" | "zonas";

export function useMapState() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const raw = sp.get("escenario") as ScenarioId | null;
  const scenario: ScenarioId = raw && SCENARIO_IDS.includes(raw) ? raw : DEFAULT_SCENARIO;
  const rawCanton = sp.get("canton");
  // El cantón de la URL debe existir en la base. Los enlaces viejos de la demostración usan otro id
  // («los-rios-vinces»): se buscan por provincia + nombre y, si no hay coincidencia, se cierra la ficha.
  const { data: areas } = useAreas("canton");
  const canton = useMemo(() => {
    if (!rawCanton) return null;
    if (!areas?.length) return UUID.test(rawCanton) || DATA_MODE === "mock" ? rawCanton : null; // aún cargando
    if (areas.some((a) => a.id === rawCanton)) return rawCanton;
    const hit = areas.find((a) => slug(`${a.province}-${a.name}`) === slug(rawCanton) || slug(a.name) === slug(rawCanton));
    return hit?.id ?? null;
  }, [rawCanton, areas]);
  const province = sp.get("provincia") || undefined;
  const layer: MapLayer = sp.get("capa") === "zonas" ? "zonas" : "perdida";
  const exportOpen = sp.get("exportar") === "1";
  const tableOpen = sp.get("tabla") === "1";
  const vista: "2d" | "satelite" = sp.get("vista") === "satelite" ? "satelite" : "2d";

  const patch = useCallback(
    (changes: Record<string, string | null | undefined>, path?: string) => {
      const next = new URLSearchParams(sp.toString());
      for (const [k, v] of Object.entries(changes)) {
        if (v == null || v === "") next.delete(k);
        else next.set(k, v);
      }
      const q = next.toString();
      router.replace(`${path ?? pathname}${q ? `?${q}` : ""}`, { scroll: false });
    },
    [sp, router, pathname],
  );

  useEffect(() => {
    if (areas?.length && rawCanton && canton !== rawCanton) patch({ canton });
  }, [areas, rawCanton, canton, patch]);

  return {
    scenario,
    canton,
    province,
    layer,
    exportOpen,
    tableOpen,
    vista,
    setVista: (v: "2d" | "satelite") => patch({ vista: v === "2d" ? null : v }),
    setScenario: (s: ScenarioId) => patch({ escenario: s }),
    selectCanton: (id: string | null) => patch({ canton: id }),
    setProvince: (p: string | null) => patch({ provincia: p }),
    setLayer: (l: MapLayer) => patch({ capa: l === "perdida" ? null : l }),
    setExportOpen: (open: boolean) => patch({ exportar: open ? "1" : null }),
    setTableOpen: (open: boolean) => patch({ tabla: open ? "1" : null }),
    patch,
  };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const slug = (s: string) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
