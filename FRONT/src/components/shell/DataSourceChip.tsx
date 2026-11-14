"use client";
import { useSWRConfig } from "swr";
import { resetBackendCheck, useDataSource } from "@/lib/api/client";
import { Icon } from "@/components/ui/Icon";

/**
 * Aviso visible cuando la app muestra datos de demostración en lugar de la API.
 * En modo "auto" es un botón: vuelve a probar el backend y recarga todos los datos.
 */
export function DataSourceChip() {
  const { mock, mode } = useDataSource();
  const { mutate } = useSWRConfig();
  if (!mock) return null;

  const body = (
    <>
      <Icon name="science" size={16} className="text-status-warn" />
      <span className="hidden sm:inline">Datos de demostración</span>
      <span className="sm:hidden">Demo</span>
    </>
  );
  const cls = "inline-flex h-8 items-center gap-1.5 rounded-sm border border-status-warn px-3 text-xs font-bold text-on-appbar";

  if (mode === "mock") {
    return <span className={cls} title="Modo demostración (NEXT_PUBLIC_DATA_MODE=mock)">{body}</span>;
  }
  return (
    <button
      type="button"
      className={`${cls} cursor-pointer hover:bg-white/10`}
      title="El backend FastAPI no respondió (BACKEND_URL). Clic para reintentar la conexión."
      onClick={() => {
        resetBackendCheck();
        void mutate(() => true);
      }}
    >
      {body}
      <Icon name="refresh" size={16} />
      <span className="sr-only">Reintentar conexión con el backend</span>
    </button>
  );
}
