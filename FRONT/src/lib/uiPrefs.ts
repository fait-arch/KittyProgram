"use client";
/** Preferencias de la interfaz que se recuerdan en este navegador (paneles ocultos, etc.). */
import { useCallback, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
const read = (key: string) => {
  try { return localStorage.getItem(key); } catch { return null; }
};

/** Booleano guardado en localStorage; `fallback` mientras no haya valor (y en el servidor). */
export function useStoredBool(key: string, fallback = false): [boolean, (v: boolean) => void] {
  const raw = useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => read(key),
    () => null,
  );
  const set = useCallback((v: boolean) => {
    try { localStorage.setItem(key, v ? "1" : "0"); } catch { /* sin almacenamiento */ }
    listeners.forEach((l) => l());
  }, [key]);
  return [raw == null ? fallback : raw === "1", set];
}
