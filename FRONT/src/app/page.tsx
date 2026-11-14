import { Suspense } from "react";
import { AppShell } from "@/components/templates/AppShell";
import { MapScreen } from "@/components/screens/MapScreen";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <AppShell active="mapa" fullBleed>
        <MapScreen />
      </AppShell>
    </Suspense>
  );
}
