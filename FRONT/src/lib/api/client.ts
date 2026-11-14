/**
 * Cliente HTTP del backend FastAPI.
 *
 * - API_BASE por defecto es /api/v1: el proxy src/app/api/v1/[...path]/route.ts lo reenvía a BACKEND_URL.
 * - DATA_MODE "auto": si el backend está apagado (503 + x-backend-down) deja de llamarlo durante
 *   30 s y responde con los datos de demostración de public/mock; si un endpoint concreto falla
 *   (404 aún no implementado, 5xx), usa la demostración solo para ese recurso. Avisa en la interfaz.
 */
import { useSyncExternalStore } from "react";
import type { ApiErrorBody } from "./types";

export type DataMode = "auto" | "api" | "mock";

export const DATA_MODE: DataMode = ((): DataMode => {
  const v = process.env.NEXT_PUBLIC_DATA_MODE;
  return v === "api" || v === "mock" ? v : "auto";
})();

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "/api/v1").replace(/\/$/, "");

/** Compatibilidad con el front anterior (AgriculturalUIDE): misma función. */
export const getBackendUrl = () => API_BASE;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: ApiErrorBody["detail"],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Params = Record<string, string | number | boolean | string[] | null | undefined>;

export function buildUrl(path: string, params?: Params): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v == null || v === "") continue;
    qs.set(k, Array.isArray(v) ? v.join(",") : String(v));
  }
  const q = qs.toString();
  return `${API_BASE}${path}${q ? `?${q}` : ""}`;
}

import { markServedFromCache } from "@/lib/offline";

// --- ¿Se están mostrando datos de demostración? (chip en la barra superior) ---
let usingMock = DATA_MODE === "mock";
const listeners = new Set<() => void>();
function setMock(v: boolean) {
  if (usingMock !== v) {
    usingMock = v;
    listeners.forEach((l) => l());
  }
}
export function useDataSource(): { mock: boolean; mode: DataMode } {
  const mock = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => usingMock,
    () => DATA_MODE === "mock",
  );
  return { mock, mode: DATA_MODE };
}

// --- Backend apagado: se prueba una vez y se reintenta cada RETRY_MS, sin llenar la consola ---
const RETRY_MS = 30_000;
let downUntil = 0;
let downNotified = false;
const warned = new Set<string>();

function backendDown() {
  downUntil = Date.now() + RETRY_MS;
  if (!downNotified) {
    downNotified = true;
    console.info(`[api] Backend no disponible: se muestran datos de demostración (se reintenta cada ${RETRY_MS / 1000} s).`);
  }
}

/** Botón «Reintentar» del chip: vuelve a probar el backend en la próxima petición. */
export function resetBackendCheck() {
  downUntil = 0;
  downNotified = false;
  warned.clear();
  setMock(DATA_MODE === "mock");
}

/** GET tipado con respaldo de demostración según DATA_MODE. */
export async function apiGet<T>(path: string, params: Params | undefined, mock: () => Promise<T>): Promise<T> {
  if (DATA_MODE === "mock") return mock();
  const auto = DATA_MODE === "auto";
  const fallback = () => {
    setMock(true);
    return mock();
  };
  if (auto && Date.now() < downUntil) return fallback();

  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    if (auto) {
      backendDown();
      return fallback();
    }
    throw new ApiError(0, "Sin conexión con el backend");
  }

  if (res.status === 503 && res.headers.get("x-backend-down")) {
    if (auto) {
      backendDown();
      return fallback();
    }
    throw new ApiError(503, "Backend no disponible");
  }

  if (!res.ok) {
    let detail: ApiErrorBody["detail"] | undefined;
    try {
      detail = ((await res.json()) as ApiErrorBody).detail;
    } catch {
      /* cuerpo vacío o no JSON */
    }
    const msg = typeof detail === "string" ? detail : res.statusText;
    if (auto) {
      // El backend responde pero este endpoint falla o aún no existe: aviso de una línea por endpoint.
      const key = `${path}:${res.status}`;
      if (!warned.has(key)) {
        warned.add(key);
        console.warn(`[api] GET ${path} respondió ${res.status}${msg ? ` (${msg})` : ""}; se usan datos de demostración para este recurso.`);
      }
      return fallback();
    }
    throw new ApiError(res.status, msg, detail);
  }

  downNotified = false;
  markServedFromCache(!!res.headers.get("x-cr-offline"));
  try {
    return (await res.json()) as T;
  } catch {
    if (auto) return fallback();
    throw new ApiError(res.status, "Respuesta no es JSON");
  }
}
