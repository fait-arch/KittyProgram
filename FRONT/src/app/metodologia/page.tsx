import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { MethodologyScreen } from "@/components/MethodologyScreen";

export const metadata: Metadata = { title: "Metodología y fuentes · CacaoResiliente" };

export default function MethodologyPage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="metodologia">
        <MethodologyScreen />
      </AppShell>
    </Suspense>
  );
}
