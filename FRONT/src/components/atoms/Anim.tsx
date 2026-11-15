/**
 * Átomo · animaciones ligeras estilo Lottie, dibujadas en SVG + CSS (sin archivos externos ni librerías).
 * Se detienen con «reducir movimiento» (ver .anim-* en globals.css).
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Mazorca de cacao que se mece: para cargas largas (mapa, alertas, ficha). */
export function CacaoLoader({ size = 56, label = "Cargando", className }: { size?: number; label?: string; className?: string }) {
  return (
    <span role="status" aria-label={label} className={cn("inline-flex flex-col items-center gap-2 text-primary", className)}>
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden className="anim-sway">
        <path d="M32 6c3 4 3 8 0 11" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <path d="M32 8c6-4 13-3 16 1-6 3-12 3-16-1Z" fill="currentColor" opacity=".55" />
        <ellipse cx="32" cy="38" rx="14" ry="21" fill="currentColor" opacity=".18" />
        <ellipse cx="32" cy="38" rx="14" ry="21" fill="none" stroke="currentColor" strokeWidth="3" />
        {[-7, 0, 7].map((x, i) => (
          <path key={x} d={`M${32 + x} 19c${x * 0.25} 12 ${x * 0.25} 26 0 38`} fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" className="anim-draw" style={{ ["--len" as string]: 40, animationDelay: `${i * 140}ms`, animationIterationCount: "infinite", animationDirection: "alternate", animationDuration: "1.2s" }} />
        ))}
      </svg>
      <span className="text-xs font-semibold text-on-surface-variant">{label}…</span>
    </span>
  );
}

/** Check que se dibuja: confirma una acción (guardado, copiado). */
export function SuccessCheck({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden className={cn("anim-pop text-primary", className)}>
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity=".16" />
      <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"
        className="anim-draw" style={{ ["--len" as string]: 18, animationDelay: "120ms" }} />
    </svg>
  );
}

/** Estado vacío: mazorca con lupa que respira. Para «sin estimación» o listas vacías. */
export function EmptyCacao({ title, children, className }: { title: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-4", className)}>
      <svg width="72" height="72" viewBox="0 0 72 72" aria-hidden className="anim-breathe shrink-0 text-primary">
        <ellipse cx="30" cy="38" rx="13" ry="20" fill="currentColor" opacity=".14" />
        <ellipse cx="30" cy="38" rx="13" ry="20" fill="none" stroke="currentColor" strokeWidth="2.5" />
        <path d="M30 18c-3 13-3 27 0 40M24 21c-2 12-2 23 0 34M36 21c2 12 2 23 0 34" fill="none" stroke="currentColor" strokeWidth="1.6" opacity=".6" />
        <circle cx="49" cy="46" r="9" fill="var(--color-surface-lowest)" stroke="currentColor" strokeWidth="2.5" />
        <path d="M55.5 52.5L63 60" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div className="flex flex-col gap-1">
        <b className="text-[15px]">{title}</b>
        {children && <span className="text-sm leading-[21px] text-on-surface-variant">{children}</span>}
      </div>
    </div>
  );
}
