import type { Metadata } from "next";
import { Suspense } from "react";
import { TemplatesScreen } from "@/components/screens/TemplatesScreen";

export const metadata: Metadata = { title: "Plantillas · CacaoResiliente" };

export default function TemplatesPage() {
  return (
    <Suspense fallback={null}>
      <TemplatesScreen />
    </Suspense>
  );
}
