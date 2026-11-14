"use client";
/**
 * Tema Misión (oscuro) / Campo (claro). Se guarda en <html data-theme> y localStorage.
 * El script THEME_INIT_SCRIPT lo aplica antes del primer pintado (ver app/layout.tsx).
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Theme } from "@/lib/design/colors";

const KEY = "cr-theme";

export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('${KEY}');if(t!=='mision'&&t!=='campo'){t=window.matchMedia('(max-width: 767px)').matches?'campo':'mision'}document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme='mision'}})();`;

const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void; toggle: () => void }>({
  theme: "mision",
  setTheme: () => {},
  toggle: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("mision");

  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    if (t === "campo" || t === "mision") setThemeState(t);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* almacenamiento no disponible */
    }
  }, []);

  const toggle = useCallback(() => setTheme(theme === "mision" ? "campo" : "mision"), [theme, setTheme]);

  return <Ctx.Provider value={{ theme, setTheme, toggle }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
