import type { MetadataRoute } from "next";

/** PWA: se instala en el teléfono del técnico y abre sin barra del navegador. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CacaoResiliente · pérdida de cacao por El Niño",
    short_name: "CacaoResiliente",
    description: "Pérdida estimada de cacao por cantón en la Costa del Ecuador (moniliasis y mazorca negra), hoy y en 2050. Funciona sin conexión con los datos guardados.",
    lang: "es-EC",
    start_url: "/?origen=app",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#07120d",
    theme_color: "#06140e",
    categories: ["agriculture", "weather", "education"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Comparar escenarios", url: "/comparar", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Plantillas para compartir", url: "/plantillas", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
