import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { FincaScreen } from "@/components/screens/FincaScreen";

export const metadata: Metadata = { title: "Mi finca · CacaoResiliente" };

export default function FincaPage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="finca" fullBleed>
        <FincaScreen />
      </AppShell>
    </Suspense>
  );
}
