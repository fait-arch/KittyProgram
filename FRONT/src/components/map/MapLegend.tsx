import type { RiskClass, Zone } from "@/lib/api/types";
import { LOSS_OUTLINE, LOSS_RAMP, RISK_CLASSES, RISK_LABEL, RISK_RANGE, ZONE_COLORS, ZONE_META, ZONES, type Theme } from "@/lib/design/colors";
import { Icon } from "@/components/ui/Icon";

/** Leyenda estilo QGIS: título, clases ascendentes, conteo. Nunca solo color. */
export function MapLegend({ mode, theme, scenarioLabel, lossCounts, zoneCounts }: {
  mode: "perdida" | "zonas";
  theme: Theme;
  scenarioLabel: string;
  lossCounts?: Record<RiskClass, number>;
  zoneCounts?: Record<Zone, number>;
}) {
  return (
    <section aria-label="Leyenda" className="w-[248px] rounded-lg border border-outline-variant bg-surface-low p-4 shadow-lg">
      {mode === "perdida" ? (
        <>
          <h3 className="font-display text-sm font-bold">Pérdida estimada (%)</h3>
          <p className="mb-2 text-xs text-on-surface-variant">{scenarioLabel} · por cantón</p>
          <ul className="flex flex-col gap-1.5">
            {RISK_CLASSES.map((c, i) => (
              <li key={c} className="flex items-center gap-2.5 text-sm">
                <span className="h-3.5 w-5 rounded-[2px]" style={{ background: LOSS_RAMP[i], boxShadow: `inset 0 0 0 1px ${LOSS_OUTLINE}` }} />
                <span className="flex-1"><span className="tabular">{RISK_RANGE[i]}</span> <span className="text-on-surface-variant">· {RISK_LABEL[c]}</span></span>
                {lossCounts && <span className="tabular text-on-surface-variant">{lossCounts[c]}</span>}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <h3 className="font-display text-sm font-bold">Matriz de zonas 2050</h3>
          <p className="mb-2 text-xs text-on-surface-variant">{scenarioLabel}</p>
          <ul className="flex flex-col gap-1.5">
            {ZONES.map((z) => (
              <li key={z} className="flex items-center gap-2.5 text-sm">
                <span className="grid h-5 w-5 place-items-center rounded-[4px]" style={{ background: ZONE_COLORS[theme][z] }} />
                <Icon name={ZONE_META[z].icon} fill size={16} />
                <span className="flex-1">{ZONE_META[z].label}</span>
                {zoneCounts && <span className="tabular text-on-surface-variant">{zoneCounts[z]}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-1.5 flex items-center gap-2.5 text-sm text-on-surface-variant">
        <span className="h-3 w-5 rounded-[2px] border border-outline bg-surface-container" />
        Fuera del alcance
      </div>
    </section>
  );
}
