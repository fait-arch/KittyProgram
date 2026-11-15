import { networkInterfaces } from "node:os";
import type { NextConfig } from "next";

// El proxy al backend FastAPI está en src/app/api/v1/[...path]/route.ts (usa BACKEND_URL).

/**
 * En desarrollo (`next dev`), Next 16 rechaza con 403 el WebSocket de recarga y los recursos
 * /_next/* cuando la página se abre desde otro host que no sea localhost (p. ej. un compañero que
 * entra por http://<tu-ip>:3000). La página se ve pero no responde a clics.
 * Se permiten automáticamente las IPs de esta máquina y, además, lo que se ponga en
 * ALLOWED_DEV_ORIGINS (separado por comas; admite comodines por segmento: 192.168.1.*, *.local).
 * No afecta a producción (`npm run build && npm start`).
 */
function devOrigins(): string[] {
  const own = Object.values(networkInterfaces())
    .flat()
    .filter((n): n is NonNullable<typeof n> => !!n && n.family === "IPv4" && !n.internal)
    .map((n) => n.address);
  const extra = (process.env.ALLOWED_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return [...new Set([...own, ...extra])];
}

/** Cabeceras de seguridad (se explican al usuario en /terminos#seguridad). */
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "SAMEORIGIN" }, // nadie puede incrustar la app (clickjacking)
  { key: "Content-Security-Policy", value: "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // Solo tiene efecto servido por HTTPS (producción)
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  allowedDevOrigins: devOrigins(),
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
