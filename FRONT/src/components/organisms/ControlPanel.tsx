"use client";
import type { AreaProps, LossItem, Scenario, ScenarioId } from "@/lib/api/types";
import { FilterChip } from "@/components/atoms/FilterChip";
import { Icon } from "@/components/atoms/Icon";
import { ScenarioSelector } from "@/components/molecules/ScenarioSelector";
import { SummaryCard } from "@/components/organisms/SummaryCard";
import { TopCantons } from "@/components/organisms/TopCantons";
import { useAreas } from "@/lib/api/hooks";


/** Panel izquierdo del mapa (escritorio): pregunta, escenario, provincia, resumen y top 5. */
export function ControlPanel(p: {
  scenario: ScenarioId;
  onScenario: (s: ScenarioId) => void;
  scenarios?: Scenario[];
  province?: string;
  onProvince: (p: string | null) => void;
  items?: LossItem[];
  areas: Map<string, AreaProps>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Con un cantón abierto, el panel se oculta en pantallas medianas para dejar espacio al mapa */
  collapsed?: boolean;
}) {
  // Provincias que hay en la base (Costa y Amazonía), ordenadas por región y nombre
  const { data: provs } = useAreas("province");
  const provinces = [...new Set((provs ?? []).map((a) => a.province || a.name))].sort((a, b) => a.localeCompare(b, "es"));
  return (
    <aside aria-label="Controles y resumen" className={`hidden w-[380px] shrink-0 flex-col gap-6 overflow-y-auto border-r border-outline-variant bg-surface p-6 no-print ${p.collapsed ? "2xl:flex" : "lg:flex"}`}>
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-[26px] leading-8 font-extrabold">¿Cuánto cacao se pierde?</h1>
        <p className="text-sm text-on-surface-variant">Pérdida estimada por enfermedades asociadas a El Niño (moniliasis y mazorca negra), por provincia y cantón.</p>
      </div>
      <ScenarioSelector value={p.scenario} onChange={p.onScenario} scenarios={p.scenarios} />
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Provincia</span>
        <div className="flex flex-wrap gap-2">
          <FilterChip selected={!p.province} onClick={() => p.onProvince(null)}>Todas</FilterChip>
          {provinces.map((pr) => (
            <FilterChip key={pr} selected={p.province === pr} onClick={() => p.onProvince(p.province === pr ? null : pr)}>{pr}</FilterChip>
          ))}
        </div>
      </div>
      <SummaryCard scenario={p.scenario} province={p.province} scenarios={p.scenarios} />
      <TopCantons items={p.items} areas={p.areas} province={p.province} selectedId={p.selectedId} onSelect={p.onSelect} />
      <p className="mt-auto flex gap-2 text-xs leading-[18px] text-on-surface-variant">
        <Icon name="info" size={18} />
        Estimación con datos NASA y estadísticas oficiales. Apoya, no reemplaza, al técnico: valide con INIAP o MAG.
      </p>
    </aside>
  );
}
