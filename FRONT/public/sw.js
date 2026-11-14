/*
 * CacaoResiliente · service worker (modo Campo sin conexión).
 * - Páginas: red primero; sin red, la última copia guardada (o la portada).
 * - /_next/static, fuentes, íconos, /mock, /geo, /qgis: caché primero (no cambian sin cambiar de nombre/versión).
 * - /api/v1 GET: red primero y se guarda la respuesta; sin red, la última respuesta guardada
 *   con la cabecera x-cr-offline: 1 para que la interfaz lo indique.
 * Para invalidar todo, subir VERSION.
 */
const VERSION = "cr-v2";
const PAGES = `${VERSION}-paginas`;
const STATIC = `${VERSION}-estaticos`;
const API = `${VERSION}-api`;
const ROUTES = ["/", "/panel", "/comparar", "/finca", "/metodologia", "/plantillas"];
const CORE = ["/mock/data.json", "/mock/cantones.geojson", "/geo/ecuador-contexto.geojson", "/manifest.webmanifest", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const pages = await caches.open(PAGES);
    const stat = await caches.open(STATIC);
    await Promise.all(CORE.map((u) => stat.add(u).catch(() => {})));
    // Cada página y los scripts/estilos que referencia
    for (const r of ROUTES) {
      try {
        const res = await fetch(r, { cache: "no-cache" });
        if (!res.ok) continue;
        await pages.put(r, res.clone());
        const html = await res.text();
        const assets = [...new Set(html.match(/\/_next\/static\/[^"'\s)]+/g) ?? [])];
        await Promise.all(assets.map((a) => stat.add(a).catch(() => {})));
      } catch { /* sin red al instalar: se llenará al navegar */ }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const k of await caches.keys()) if (!k.startsWith(VERSION)) await caches.delete(k);
    await self.clients.claim();
  })());
});

const isStatic = (url) =>
  url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/mock/") || url.pathname.startsWith("/geo/") ||
  url.pathname.startsWith("/qgis/") || url.pathname.startsWith("/icons/") || url.pathname === "/manifest.webmanifest" ||
  url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";

async function cacheFirst(req) {
  const c = await caches.open(STATIC);
  const hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok || res.type === "opaque") c.put(req, res.clone());
  return res;
}

async function networkFirst(req, cacheName, markOffline) {
  const c = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) {
      c.put(req, res.clone());
      return res;
    }
    // Backend apagado (503 del proxy): mejor la última respuesta real guardada que datos de demostración
    if (markOffline && res.status === 503) {
      const hit = await c.match(req, { ignoreVary: true });
      if (hit) return offlineCopy(hit);
    }
    return res;
  } catch (err) {
    const hit = await c.match(req, { ignoreVary: true });
    if (!hit) throw err;
    return markOffline ? offlineCopy(hit) : hit;
  }
}

function offlineCopy(hit) {
  const h = new Headers(hit.headers);
  h.set("x-cr-offline", "1");
  return new Response(hit.body, { status: hit.status, statusText: hit.statusText, headers: h });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req, PAGES, false).catch(async () => (await caches.match(url.pathname)) ?? (await caches.match("/"))));
    return;
  }
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/v1/")) {
    if (url.pathname.startsWith("/api/v1/export")) return; // archivos grandes: siempre a la red
    event.respondWith(networkFirst(req, API, true));
    return;
  }
  if (isStatic(url)) event.respondWith(cacheFirst(req));
});
