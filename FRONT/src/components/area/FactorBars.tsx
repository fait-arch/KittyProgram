import type { Factor } from "@/lib/api/types";
import { fmt1, fmtInt } from "@/lib/design/format";

/** "¿Por qué?": contribución de cada factor en lenguaje de finca (un solo tono). */
export function FactorBars({ factors }: { factors: Factor[] }) {
  const max = Math.max(...factors.map((f) => f.contribution_pct), 1);
  return (
    <section aria-label="Por qué" className="flex flex-col gap-3.5">
      <div>
        <h2 className="font-display text-xl font-bold">¿Por qué?</h2>
        <p className="text-[13px] text-on-surface-variant">Lo que más suma a la pérdida, en puntos porcentuales</p>
      </div>
      {factors.map((f) => (
        <div key={f.feature} className="flex flex-col gap-1.5">
          <div className="flex items-baseline gap-3">
            <span className="flex-1 text-[15px] font-semibold leading-5">{f.label}</span>
            <span className="font-display text-base font-extrabold tabular">+{fmt1(f.contribution_pct)} pts</span>
          </div>
          <div className="h-2.5 rounded-r bg-surface-high" title={`${f.label}: +${fmt1(f.contribution_pct)} puntos`}>
            <div className="h-2.5 rounded-r bg-primary" style={{ width: `${(f.contribution_pct / max) * 100}%` }} />
          </div>
          <span className="text-xs text-on-surface-muted">{fmtInt(f.value)} {f.unit} · {f.source}</span>
        </div>
      ))}
      <span className="text-xs text-on-surface-muted">Contribuciones del modelo (SHAP).</span>
    </section>
  );
}
