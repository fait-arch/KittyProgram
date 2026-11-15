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
    <header className="flex min-h-16 flex-wrap items-center gap-x-6 gap-y-2 border-b border-appbar-outline bg-appbar px-4 py-2 text-on-appbar no-print lg:pl-5">
      <Link href="/" className="flex items-center gap-3">
        <Logo />
        <span className="flex flex-col">
          <span className="font-display text-xl font-extrabold leading-6">CacaoResiliente</span>
          <span className="hidden text-[11px] font-semibold uppercase leading-4 tracking-[0.8px] text-on-appbar-variant sm:block">Field Shift · NASA Space Apps 2026</span>
        </span>
      </Link>
      <div className="order-last hidden w-full justify-center md:order-none md:flex md:w-auto md:flex-1">
        <CantonSearch />
      </div>
      <div className="ml-auto flex items-center gap-1 md:ml-0">
        <DataSourceChip />
        <WhatsAppButton variant="bar" className="mr-1" />
        {install && (
          <IconButton icon="install_mobile" label="Instalar la app (funciona sin conexión)" onClick={install} className="text-on-appbar-variant hover:bg-white/10" />
        )}
        <Link href="/metodologia" aria-label="Metodología y fuentes" title="Metodología y fuentes"
          className="grid size-12 place-items-center rounded-full text-on-appbar-variant hover:bg-white/10">
          <span className="ms" aria-hidden>help</span>
        </Link>
        <IconButton
          icon={theme === "mision" ? "light_mode" : "dark_mode"}
          label={theme === "mision" ? "Cambiar a tema Campo (claro)" : "Cambiar a tema Misión (oscuro)"}
          onClick={toggle}
          className="text-on-appbar-variant hover:bg-white/10"
        />
        <span className="hidden sm:inline-flex">
          <Button variant="tonal" icon="download" onClick={onExport} className="!bg-appbar-container !text-on-appbar">
            Exportar · QGIS
          </Button>
        </span>
        <span className="sm:hidden">
          <IconButton icon="download" label="Exportar" onClick={onExport} className="text-on-appbar-variant hover:bg-white/10" />
        </span>
      </div>
    </header>
  );
}
