import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { CompareScreen } from "@/components/screens/CompareScreen";

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
