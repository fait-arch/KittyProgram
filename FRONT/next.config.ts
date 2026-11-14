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

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: devOrigins(),
};

export default nextConfig;
