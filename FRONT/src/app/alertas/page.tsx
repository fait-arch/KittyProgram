import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { AlertsScreen } from "@/components/screens/AlertsScreen";

export const metadata: Metadata = { title: "Alertas · CacaoResiliente" };

export default function AlertasPage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="alertas">
        <AlertsScreen />
      </AppShell>
    </Suspense>
  );
}
