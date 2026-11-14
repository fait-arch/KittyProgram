"use client";
import Link from "next/link";
import { useOnline, useSavedCantons, useServedFromCache } from "@/lib/offline";
import { Icon } from "@/components/atoms/Icon";

/**
 * Organismo · aviso de modo sin conexión. Dos casos:
 *  - el dispositivo no tiene red → se ven los datos guardados (y accesos a los cantones guardados);
 *  - hay red pero el servidor no responde → se ven las últimas respuestas reales guardadas.
 */
export function OfflineBanner() {
  const online = useOnline();
  const cached = useServedFromCache();
  const saved = useSavedCantons();
  if (online && !cached) return null;
  return (
    <div role="status" className="no-print flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-outline-variant bg-surface-highest px-4 py-2 text-sm lg:px-6">
      <Icon name={online ? "cloud_off" : "wifi_off"} size={20} className="text-status-warn" />
      <span className="font-semibold">{online ? "El servidor no responde" : "Sin conexión"}</span>
      <span className="text-on-surface-variant">
        {online ? "Se muestran los últimos datos reales guardados en este dispositivo." : "Se muestran los datos guardados en este dispositivo; pueden no ser los más recientes."}
      </span>
      {!online && saved.length > 0 && (
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-on-surface-variant">Guardados:</span>
          {saved.slice(0, 6).map((c) => (
            <Link key={c.id} href={`/?canton=${encodeURIComponent(c.id)}`} className="state-layer inline-flex h-7 items-center gap-1 rounded-sm bg-secondary-container px-2.5 text-[13px] font-semibold text-on-secondary-container">
              <Icon name="offline_pin" size={16} />{c.name}
            </Link>
          ))}
        </span>
      )}
    </div>
  );
}
