"use client";
import type { Scenario, ScenarioId } from "@/lib/api/types";
import { SegmentedButton } from "@/components/ui/SegmentedButton";

const SHORT: Record<ScenarioId, string> = {
  normal: "Normal",
  nino: "Año Niño",
  actual: "Actual",
  ssp245_2050: "SSP2-4.5",
  ssp585_2050: "SSP5-8.5",
};

/** Escenario: hoy (Fase 1) y clima 2041–2060 (Fase 2). Una sola selección global. */
export function ScenarioSelector({ value, onChange, scenarios, compact }: {
  value: ScenarioId;
  onChange: (s: ScenarioId) => void;
  scenarios?: Scenario[];
  compact?: boolean;
}) {
  const avail = (id: ScenarioId) => scenarios?.find((s) => s.id === id)?.available ?? true;
  const hoy: ScenarioId[] = ["normal", "nino", "actual"];
  const fut: ScenarioId[] = ["ssp245_2050", "ssp585_2050"];
  if (compact) {
    return (
      <SegmentedButton
        label="Escenario"
        value={value}
        onChange={onChange}
        options={[...hoy, "ssp245_2050" as ScenarioId].map((id) => ({ value: id, label: id === "ssp245_2050" ? "2050" : SHORT[id], disabled: !avail(id) }))}
      />
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Escenario · hoy</span>
      <SegmentedButton label="Escenario de hoy" value={hoy.includes(value) ? value : null} onChange={onChange}
        options={hoy.map((id) => ({ value: id, label: SHORT[id], disabled: !avail(id) }))} />
      <span className="mt-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
        Clima 2041–2060
        <span className="rounded-full bg-neon-yellow px-1.5 font-display text-[10px] font-extrabold leading-4 tracking-normal text-deep-blue">FASE 2</span>
      </span>
      <SegmentedButton label="Escenario 2050" value={fut.includes(value) ? value : null} onChange={onChange}
        options={fut.map((id) => ({ value: id, label: SHORT[id], disabled: !avail(id) }))} />
    </div>
  );
}
