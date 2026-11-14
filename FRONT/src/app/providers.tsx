"use client";
import { useEffect, type ReactNode } from "react";
import { ThemeProvider } from "@/lib/theme";
import { registerServiceWorker } from "@/lib/offline";

export function Providers({ children }: { children: ReactNode }) {
  // Muestra los íconos solo cuando la fuente cargó (si no, se vería el nombre del ícono como texto).
  useEffect(() => registerServiceWorker(), []);
  useEffect(() => {
    document.fonts?.load('24px "Material Symbols Rounded"', "map").then((f) => {
      if (f.length) document.documentElement.classList.add("ms-ready");
    }).catch(() => {});
  }, []);
  return <ThemeProvider>{children}</ThemeProvider>;
}
