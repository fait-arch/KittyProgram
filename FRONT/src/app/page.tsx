import { Suspense } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { MapScreen } from "@/components/map/MapScreen";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <AppShell active="mapa" fullBleed>
        <MapScreen />
      </AppShell>
    </Suspense>
  );
}
