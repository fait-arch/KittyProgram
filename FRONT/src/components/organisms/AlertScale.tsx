import { RISK_CLASSES, RISK_LABEL, RISK_META, RISK_RANGE, ZONE_COLORS, ZONE_META, ZONES, type LossLevel, type Theme } from "@/lib/design/colors";
import { Icon } from "@/components/atoms/Icon";
import { Swatch } from "@/components/atoms/Swatch";

/**
 * Organismo · explica qué significa cada color.
 * Pérdida: fases IPC (FAO/FEWS NET) + alertas SNGR. Zonas: semáforo con verde azulado para "Segura".
 */
export function AlertScale({ theme }: { theme: Theme }) {
  return (
    <section id="colores" className="flex scroll-mt-4 flex-col gap-4">
      <h2 className="font-display text-xl font-bold">¿Qué significa cada color?</h2>
      <p className="leading-6 text-on-surface-variant">
        La pérdida usa los mismos colores que la Clasificación Integrada de Fases (IPC) de la FAO y el semáforo de alertas de la
        Secretaría de Gestión de Riesgos (amarilla, naranja y roja). El nivel <b className="text-on-surface">Crítico</b> lleva rayado para
        que se distinga sin depender del color, en pantalla, impreso y en QGIS.
      </p>
      <ol className="grid gap-2 sm:grid-cols-5">
        {RISK_CLASSES.map((c, i) => (
          <li key={c} className="flex flex-col gap-2 rounded-md bg-surface-high p-3">
            <Swatch level={i as LossLevel} className="!h-8 !w-full !rounded-sm" />
            <span className="flex items-center gap-1.5 font-display text-base font-extrabold">
              <Icon name={RISK_META[c].icon} fill size={18} className="text-on-surface-variant" />
              {RISK_LABEL[c]}
            </span>
            <span className="text-sm tabular">{RISK_RANGE[i]} %</span>
            <span className="text-xs text-on-surface-variant">{RISK_META[c].ipc} · {RISK_META[c].alert}</span>
            <span className="text-xs leading-[18px]">{RISK_META[c].meaning}</span>
          </li>
        ))}
      </ol>
      <ul className="grid gap-2 sm:grid-cols-4">
        {ZONES.map((z) => (
          <li key={z} className="flex items-start gap-2.5 rounded-md border border-outline-variant p-3">
            <Swatch color={ZONE_COLORS[theme][z]} size="lg" className="mt-0.5" />
            <span className="flex flex-col">
              <span className="flex items-center gap-1 font-bold"><Icon name={ZONE_META[z].icon} fill size={16} />{ZONE_META[z].label}</span>
              <span className="text-xs text-on-surface-variant">{ZONE_META[z].quadrant}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
