import { LOSS_RAMP, HATCH_LEVEL } from "@/lib/design/colors";

/**
 * Átomo · definición SVG del rayado del nivel Crítico.
 * Se monta una vez en el layout; Leaflet lo usa con fillColor "url(#cr-hatch)".
 * Igual que la capa LinePatternFill (45°, blanco 70 %) de qgis/estilos/perdida_cacao.qml.
 */
export function HatchDefs() {
  return (
    <svg aria-hidden width="0" height="0" style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }} focusable="false">
      <defs>
        <pattern id="cr-hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <rect width="6" height="6" fill={LOSS_RAMP[HATCH_LEVEL]} />
          <line x1="0" y1="0" x2="0" y2="6" stroke="#ffffff" strokeOpacity="0.7" strokeWidth="2" />
        </pattern>
      </defs>
    </svg>
  );
}
