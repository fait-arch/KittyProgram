import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { TermsScreen } from "@/components/screens/TermsScreen";

export const metadata: Metadata = { title: "Términos, privacidad y seguridad · CacaoResiliente" };

export default function TermsPage() {
  return (
    <Suspense fallback={null}>
      <AppShell active="metodologia">
        <TermsScreen />
      </AppShell>
    </Suspense>
  );
}
