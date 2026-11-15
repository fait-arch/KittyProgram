"use client";
import Link from "next/link";
import { useTheme } from "@/lib/theme";
import { useInstallPrompt } from "@/lib/offline";
import { Button, IconButton } from "@/components/atoms/Button";
import { Logo } from "@/components/atoms/Logo";
import { CantonSearch } from "@/components/molecules/CantonSearch";
import { DataSourceChip } from "@/components/molecules/DataSourceChip";
import { WhatsAppButton } from "@/components/molecules/WhatsAppButton";

/** Barra superior M3. Siempre Deep Blue (ancla de marca) en los dos temas. */
export function TopAppBar({ onExport }: { onExport: () => void }) {
  const { theme, toggle } = useTheme();
  const install = useInstallPrompt();
  return (
    <header className="border-b border-appbar-outline bg-appbar text-on-appbar no-print">
      <div className="flex min-h-14 items-center gap-2 px-2 py-1.5 sm:min-h-16 sm:gap-6 sm:px-4 lg:pl-5">
        <Link href="/" className="flex min-w-0 items-center gap-2 sm:gap-3" aria-label="CacaoResiliente · inicio">
          <Logo />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-display text-lg font-extrabold leading-6 sm:text-xl">CacaoResiliente</span>
            <span className="hidden text-[11px] font-semibold uppercase leading-4 tracking-[0.8px] text-on-appbar-variant sm:block">Field Shift · NASA Space Apps 2026</span>
          </span>
        </Link>
        <div className="hidden md:flex md:flex-1 md:justify-center">
          <CantonSearch />
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1 md:ml-0">
          <DataSourceChip />
          <WhatsAppButton variant="bar" className="mr-0.5 sm:mr-1" />
          {install && (
            <IconButton icon="install_mobile" label="Instalar la app (funciona sin conexión)" onClick={install} className="hidden !text-on-appbar-variant hover:bg-white/10 sm:grid" />
          )}
          <Link href="/metodologia" aria-label="Metodología y fuentes" title="Metodología y fuentes"
            className="grid size-11 place-items-center rounded-full text-on-appbar-variant hover:bg-white/10 sm:size-12">
            <span className="ms" aria-hidden>help</span>
          </Link>
          <IconButton
            icon={theme === "mision" ? "light_mode" : "dark_mode"}
            label={theme === "mision" ? "Cambiar a tema Campo (claro)" : "Cambiar a tema Misión (oscuro)"}
            onClick={toggle}
            className="!text-on-appbar-variant hover:bg-white/10"
          />
          <span className="hidden sm:inline-flex">
            <Button variant="tonal" icon="download" onClick={onExport} className="!bg-appbar-container !text-on-appbar">
              Exportar · QGIS
            </Button>
          </span>
          <span className="sm:hidden">
            <IconButton icon="download" label="Exportar" onClick={onExport} className="!text-on-appbar-variant hover:bg-white/10" />
          </span>
        </div>
      </div>
      {/* En móvil el buscador baja a su propia fila, a todo el ancho */}
      <div className="px-3 pb-2 md:hidden">
        <CantonSearch />
      </div>
    </header>
  );
}
