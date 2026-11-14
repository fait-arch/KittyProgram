import { cn } from "@/lib/cn";

/** Átomo · marcador de carga (respeta prefers-reduced-motion vía motion-safe). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-md bg-surface-highest motion-safe:animate-pulse", className)} />;
}
