import type { Metadata, Viewport } from "next";
import "@fontsource/fira-sans/400.css";
import "@fontsource/fira-sans/600.css";
import "@fontsource/fira-sans/700.css";
import "@fontsource/fira-sans/800.css";
import "@fontsource/fira-sans/900.css";
import "@fontsource/overpass/300.css";
import "@fontsource/overpass/400.css";
import "@fontsource/overpass/600.css";
import "@fontsource/overpass/700.css";
import "@fontsource/fira-code/400.css";
import "./globals.css";
import { Providers } from "./providers";
import { HatchDefs } from "@/components/atoms/HatchDefs";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: "CacaoResiliente · Pérdida de cacao por El Niño",
  description: "¿Cuánta producción de cacao se perdería en cada cantón del Ecuador por enfermedades asociadas a El Niño, hoy y con el clima de 2050? NASA Space Apps Challenge 2026 · Field Shift.",
  applicationName: "CacaoResiliente",
  appleWebApp: { capable: true, title: "CacaoResiliente", statusBarStyle: "black-translucent" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#06140e",
  width: "device-width",
  initialScale: 1,
};

// Material Symbols Rounded: solo los íconos que usa la app (parámetro icon_names, orden alfabético).
const ICONS = [
  "add", "arrow_forward", "check", "check_box", "check_circle", "close", "compare", "compare_arrows", "dangerous", "dark_mode",
  "download", "error", "expand_less", "expand_more", "handyman", "help", "info", "layers", "light_mode", "map",
  "picture_as_pdf", "radio_button_checked", "radio_button_unchecked", "refresh", "remove", "report", "science", "search", "share",
  "swap_horiz", "table_rows", "table_view", "thunderstorm", "touch_app", "trending_down", "trending_up", "verified",
  "warning", "waves", "zoom_out_map", "agriculture", "arrow_back", "hourglass_top", "ios_share", "monitoring", "print", "cloud_off", "download_for_offline", "install_mobile", "offline_pin", "wifi_off", "bookmark_add", "delete", "my_location", "pin_drop", "polyline", "undo", "eco", "landscape", "public", "view_in_ar", "rainy", "forest", "local_fire_department", "device_thermostat", "air", "straighten", "dashboard", "satellite_alt", "notifications_active", "payments", "grass", "trending_flat", "bolt", "tips_and_updates", "priority_high", "water_drop", "partly_cloudy_day", "image",
].sort();
const ICON_FONT = `https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&icon_names=${ICONS.join(",")}&display=block`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" data-theme="mision" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={ICON_FONT} />
      </head>
      <body>
        <HatchDefs />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
