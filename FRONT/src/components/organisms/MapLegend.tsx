import type { RiskClass, Zone } from "@/lib/api/types";
import { MAP_THEME, RISK_CLASSES, RISK_LABEL, RISK_RANGE, ZONE_COLORS, ZONE_META, ZONES, type LossLevel, type Theme } from "@/lib/design/colors";
import { Icon } from "@/components/atoms/Icon";
import { Swatch } from "@/components/atoms/Swatch";
import { LegendItem } from "@/components/molecules/LegendItem";

/**
 * Organismo · leyenda estilo QGIS: título, clases ascendentes, conteo. Nunca solo color.
 * Escala de alerta de 5 niveles (IPC / SNGR); Crítica lleva rayado.
 */
export function MapLegend({ mode, theme, scenarioLabel, lossCounts, zoneCounts, noDataCount }: {
  mode: "perdida" | "zonas";
  theme: Theme;
  scenarioLabel: string;
  lossCounts?: Record<RiskClass, number>;
  zoneCounts?: Record<Zone, number>;
  /** cantones de la base sin estimación del modelo (p. ej. Amazonía) */
  noDataCount?: number;
}) {
  return (
    <section aria-label="Leyenda" className="w-[248px] rounded-lg border border-outline-variant bg-surface-low p-4 shadow-lg">
      {mode === "perdida" ? (
        <>
          <h3 className="font-display text-sm font-bold">Pérdida estimada (%)</h3>
          <p className="mb-2 text-xs text-on-surface-variant">{scenarioLabel} · por cantón</p>
          <ul className="flex flex-col gap-1.5">
            {RISK_CLASSES.map((c, i) => (
              <LegendItem key={c} swatch={<Swatch level={i as LossLevel} />} range={RISK_RANGE[i]} label={RISK_LABEL[c]} count={lossCounts?.[c]} />
            ))}
          </ul>
        </>
      ) : (
        <>
          <h3 className="font-display text-sm font-bold">Matriz de zonas 2050</h3>
          <p className="mb-2 text-xs text-on-surface-variant">{scenarioLabel}</p>
          {zoneCounts && Object.values(zoneCounts).every((v) => !v) && (
            <p className="mb-2 rounded-md bg-surface-high p-2 text-xs leading-[17px] text-on-surface-variant">
              Las zonas 2050 todavía no están cargadas en la base de datos (proyecciones NASA CMIP6).
            </p>
          )}
          <ul className="flex flex-col gap-1.5">
            {ZONES.map((z) => (
              <LegendItem key={z} swatch={<><Swatch color={ZONE_COLORS[theme][z]} size="lg" /><Icon name={ZONE_META[z].icon} fill size={16} /></>}
                label={ZONE_META[z].label} count={zoneCounts?.[z]} />
            ))}
          </ul>
        </>
      )}
      <div className="mt-1.5 flex items-center gap-2.5 text-sm text-on-surface-variant">
        <span className="h-3.5 w-5 rounded-[3px] border-2" style={{ background: MAP_THEME[theme].noData, borderColor: MAP_THEME[theme].province }} />
        <span className="flex-1">Sin estimación del modelo</span>
        {noDataCount != null && <span className="tabular">{noDataCount}</span>}
      </div>
      <div className="flex items-center gap-2.5 text-sm text-on-surface-variant">
        <span className="h-3.5 w-5 rounded-[3px] border border-outline bg-surface-container" />
        Fuera de la base de datos
      </div>
    </section>
  );
}
