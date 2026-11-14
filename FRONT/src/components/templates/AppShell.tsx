"use client";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { useMapState } from "@/lib/state/useMapState";
import { ExportDialog } from "@/components/organisms/ExportDialog";
import { TopAppBar } from "@/components/organisms/TopAppBar";
import { EnsoBanner } from "@/components/organisms/EnsoBanner";
import { OfflineBanner } from "@/components/organisms/OfflineBanner";
import { NavBar, NavRail, type NavKey } from "@/components/organisms/Navigation";

/** Estructura común: barra superior + banner ENSO + riel (escritorio) / barra inferior (móvil). */
export function AppShell({ active, children, fullBleed }: { active: NavKey; children: ReactNode; fullBleed?: boolean }) {
  const { exportOpen, setExportOpen } = useMapState();
  return (
    <div className="flex h-dvh flex-col">
      <TopAppBar onExport={() => setExportOpen(true)} />
      <EnsoBanner />
      <OfflineBanner />
      <div className="flex min-h-0 flex-1">
        <NavRail active={active} />
        <main className={cn("min-h-0 min-w-0 flex-1", fullBleed ? "relative overflow-hidden pb-20 lg:pb-0" : "overflow-y-auto pb-24 lg:pb-0")}>
          {children}
        </main>
      </div>
      <NavBar active={active} />
      <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
    </div>
  );
}
