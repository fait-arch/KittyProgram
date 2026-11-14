import { HATCH_LEVEL, LOSS_OUTLINE, lossClassIndex, lossColor } from "@/lib/design/colors";
import { fmtPct, fmtPctRange } from "@/lib/design/format";
import { cn } from "@/lib/cn";

/**
 * Molécula · rango probable p10–p90 con la estimación central.
 * Las marcas de 15/30/45 % muestran dónde cambia el nivel de alerta.
 */
export function LossInterval({ low, mid, high }: { low: number; mid: number; high: number }) {
  const max = Math.max(50, Math.ceil(high / 10) * 10);
  const x = (v: number) => `${(Math.min(v, max) / max) * 100}%`;
  const color = lossColor(mid);
  const hatch = lossClassIndex(mid) === HATCH_LEVEL;
  return (
    <div className="flex flex-col gap-1.5">
      <div role="img" aria-label={`Rango probable entre ${fmtPctRange(low, high)}; estimación central ${fmtPct(mid)}`} className="relative h-6">
        <div className="absolute inset-x-0 top-[9px] h-1.5 rounded-full bg-outline-variant" />
        {[5, 15, 30, 45].filter((b) => b < max).map((b) => (
          <div key={b} className="absolute top-[5px] h-3.5 w-px bg-on-surface-muted/50" style={{ left: x(b) }} />
        ))}
        <div className="absolute top-1.5 h-3 rounded-full opacity-60" style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})`, background: color }} />
        <div className={cn("absolute top-[3px] size-[18px] -ml-[9px] rounded-full ring-2 ring-surface-high", hatch && "hatch-critica")}
          style={{ left: x(mid), background: hatch ? undefined : color, boxShadow: `0 0 0 3px ${LOSS_OUTLINE}33` }} />
      </div>
      <div className="flex justify-between text-[11px] text-on-surface-muted tabular"><span>0 %</span><span>{max / 2} %</span><span>{max} %</span></div>
    </div>
  );
}
