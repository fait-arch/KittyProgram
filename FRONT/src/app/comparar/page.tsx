import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { CompareScreen } from "@/components/compare/CompareScreen";

export const metadata: Metadata = { title: "Comparar escenarios · CacaoResiliente" };

export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="comparar">
        <CompareScreen />
      </AppShell>
    </Suspense>
  );
}
