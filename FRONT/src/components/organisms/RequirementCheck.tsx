import type { AreaClimate, CropRequirements, RequirementParam } from "@/lib/api/types";
import { STATUS, type StatusKey } from "@/lib/design/colors";
import { fmt1, fmtInt } from "@/lib/design/format";
import { Icon } from "@/components/atoms/Icon";

const VALUE: Record<RequirementParam["id"], (c: AreaClimate) => number | null> = {
  temp_mean: (c) => c.temp_mean_c,
  rain_annual: (c) => c.rain_annual_mm,
  elevation: (c) => c.elevation_m,
  soil_ph: (c) => c.soil_ph,
};

function status(v: number, p: RequirementParam): StatusKey {
  const inOpt = (p.optimal_min == null || v >= p.optimal_min) && (p.optimal_max == null || v <= p.optimal_max);
  if (inOpt) return "ok";
  const outAbs = (p.absolute_min != null && v < p.absolute_min) || (p.absolute_max != null && v > p.absolute_max);
  return outAbs ? "out" : "warn";
}

const fmtVal = (v: number, p: RequirementParam) => `${p.id === "soil_ph" ? fmt1(v) : fmtInt(v)}${p.unit ? ` ${p.unit}` : ""}`;

/** Clima de la zona vs requerimientos ECOCROP (✓ / ⚠ / ✗ con ícono y texto). */
export function RequirementCheck({ climate, req }: { climate: AreaClimate; req: CropRequirements }) {
  return (
    <section aria-label="Clima frente a lo que necesita el cacao" className="flex flex-col gap-3.5">
      <div>
        <h2 className="font-display text-xl font-bold">Clima vs lo que necesita el cacao</h2>
        <p className="text-[13px] text-on-surface-variant">Banda = rango óptimo ({req.source}) · punto = valor de la zona</p>
      </div>
      {req.parameters.map((p) => {
        const v = VALUE[p.id](climate);
        if (v == null) return null;
        const lo = p.absolute_min ?? Math.min(p.optimal_min ?? v, v) * 0.8;
        const hi = p.absolute_max ?? Math.max(p.optimal_max ?? v, v) * 1.25;
        const pos = (x: number) => `${Math.min(100, Math.max(0, ((x - lo) / (hi - lo)) * 100))}%`;
        const s = status(v, p);
        const opt = `${p.optimal_min != null ? fmtVal(p.optimal_min, p).replace(` ${p.unit}`, "") : "0"}–${p.optimal_max != null ? fmtVal(p.optimal_max, p) : ""}`;
        return (
          <div key={p.id} className="grid grid-cols-[150px_minmax(0,1fr)_140px] items-center gap-3">
            <div className="flex flex-col">
              <span className="text-sm font-semibold">{p.label}</span>
              <span className="text-xs text-on-surface-muted">óptimo {opt}</span>
            </div>
            <div className="relative h-4" role="img" aria-label={`${p.label}: ${fmtVal(v, p)}; óptimo ${opt}; ${STATUS[s].label}`}>
              <div className="absolute inset-x-0 top-1.5 h-1 rounded-full bg-outline-variant" />
              <div className="absolute top-1 h-2 rounded-full bg-primary/50"
                style={{ left: pos(p.optimal_min ?? lo), width: `calc(${pos(p.optimal_max ?? hi)} - ${pos(p.optimal_min ?? lo)})` }} />
              <div className="absolute top-px size-3.5 -ml-[7px] rounded-full ring-2 ring-surface-low" style={{ left: pos(v), background: s === "ok" ? "var(--color-on-surface)" : STATUS[s].color }} />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="shrink-0" style={{ color: STATUS[s].color }}><Icon name={STATUS[s].icon} fill size={20} /></span>
              <span className="flex flex-col">
                <b className="font-display text-sm tabular">{fmtVal(v, p)}</b>
                <span className="text-xs text-on-surface-variant">{STATUS[s].label}</span>
              </span>
            </div>
          </div>
        );
      })}
    </section>
  );
}
