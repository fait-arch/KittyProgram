import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { PanelScreen } from "@/components/screens/PanelScreen";

export const metadata: Metadata = { title: "Panel general · CacaoResiliente" };

export default function PanelPage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="panel">
        <PanelScreen />
      </AppShell>
    </Suspense>
  );
}
