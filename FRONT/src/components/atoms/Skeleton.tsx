import { cn } from "@/lib/cn";

/** Átomo · marcador de carga: un brillo suave que recorre el bloque (sin parpadeo; respeta «reducir movimiento»). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("shimmer rounded-md", className)} />;
}
