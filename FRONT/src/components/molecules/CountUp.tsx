"use client";
import { useEffect, useRef, useState } from "react";

/** Molécula · cifra que sube hasta su valor (efecto principal del encabezado). Sin animación si se pide reducir movimiento. */
export function CountUp({ value, format, duration = 900 }: { value: number | null | undefined; format: (v: number) => string; duration?: number }) {
  const [shown, setShown] = useState<number | null>(null);
  const from = useRef(0);
  useEffect(() => {
    if (value == null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(value); return; }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / duration);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(a + (value - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <>{value == null ? "—" : format(shown ?? 0)}</>;
}
