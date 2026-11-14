"use client";
/**
 * Modo Campo sin conexión (PWA): service worker, estado de la red, datos servidos desde la caché,
 * instalación y cantones guardados para usar sin señal.
 */
import { useEffect, useState, useSyncExternalStore } from "react";

// --- ¿La última respuesta de la API salió de la caché del service worker? ---
let fromCache = false;
const cacheListeners = new Set<() => void>();
export function markServedFromCache(v: boolean) {
  if (fromCache !== v) {
    fromCache = v;
    cacheListeners.forEach((l) => l());
  }
}
export function useServedFromCache() {
  return useSyncExternalStore((l) => (cacheListeners.add(l), () => cacheListeners.delete(l)), () => fromCache, () => false);
}

// --- Conexión del dispositivo ---
export function useOnline() {
  return useSyncExternalStore(
    (l) => {
      window.addEventListener("online", l);
      window.addEventListener("offline", l);
      return () => {
        window.removeEventListener("online", l);
        window.removeEventListener("offline", l);
      };
    },
    () => navigator.onLine,
    () => true,
  );
}

// --- Registro del service worker (solo en producción: `npm run demo` / `next start`) ---
export function registerServiceWorker() {
  if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
  if (process.env.NEXT_PUBLIC_SW === "off") return;
  navigator.serviceWorker.register("/sw.js").catch((e) => console.info("[sw] no se pudo registrar:", e));
}

// --- Instalar la app (Chrome/Android: beforeinstallprompt) ---
type BIP = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
export function useInstallPrompt() {
  const [evt, setEvt] = useState<BIP | null>(null);
  useEffect(() => {
    const on = (e: Event) => { e.preventDefault(); setEvt(e as BIP); };
    const done = () => setEvt(null);
    window.addEventListener("beforeinstallprompt", on);
    window.addEventListener("appinstalled", done);
    return () => { window.removeEventListener("beforeinstallprompt", on); window.removeEventListener("appinstalled", done); };
  }, []);
  return evt ? async () => { await evt.prompt(); await evt.userChoice; setEvt(null); } : null;
}

// --- Cantones guardados para usar sin conexión ---
const KEY = "cr-offline-cantones";
export type SavedCanton = { id: string; name: string; savedAt: string };
const savedListeners = new Set<() => void>();
let savedCache: SavedCanton[] | null = null;
function readSaved(): SavedCanton[] {
  if (savedCache) return savedCache;
  try { savedCache = JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { savedCache = []; }
  return savedCache!;
}
function writeSaved(list: SavedCanton[]) {
  savedCache = list;
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* sin almacenamiento */ }
  savedListeners.forEach((l) => l());
}
const EMPTY: SavedCanton[] = [];
export function useSavedCantons() {
  return useSyncExternalStore((l) => (savedListeners.add(l), () => savedListeners.delete(l)), readSaved, () => EMPTY);
}
export function markCantonSaved(c: { id: string; name: string }) {
  writeSaved([{ ...c, savedAt: new Date().toISOString() }, ...readSaved().filter((x) => x.id !== c.id)].slice(0, 20));
}
export function forgetCanton(id: string) {
  writeSaved(readSaved().filter((x) => x.id !== id));
}
