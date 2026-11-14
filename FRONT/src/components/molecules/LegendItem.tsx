import type { ReactNode } from "react";

/** Molécula · fila de leyenda estilo QGIS: símbolo + rango + etiqueta + conteo. */
export function LegendItem({ swatch, range, label, count, className }: {
  swatch: ReactNode;
  range?: string;
  label: ReactNode;
  count?: number;
  className?: string;
}) {
  return (
    <li className={`flex items-center gap-2.5 text-sm ${className ?? ""}`}>
      {swatch}
      <span className="flex-1">
        {range && <span className="tabular">{range} %</span>} {range && <span className="text-on-surface-variant">· </span>}
        <span className={range ? "text-on-surface-variant" : undefined}>{label}</span>
      </span>
      {count != null && <span className="tabular text-on-surface-variant">{count}</span>}
    </li>
  );
}
