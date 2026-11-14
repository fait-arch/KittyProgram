"use client";
import { useState } from "react";
import { saveCantonOffline } from "@/lib/offlineSave";
import { useOnline, useSavedCantons } from "@/lib/offline";
import { Button } from "@/components/atoms/Button";

const fmtDate = (iso: string) => new Intl.DateTimeFormat("es-EC", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));

/**
 * Molécula · «Guardar sin conexión»: descarga los datos del cantón (5 escenarios) antes de salir al campo.
 * Muestra el avance y, una vez guardado, la fecha; volver a pulsar actualiza la copia.
 */
export function SaveOfflineButton({ id, name }: { id: string; name: string }) {
  const online = useOnline();
  const saved = useSavedCantons().find((c) => c.id === id);
  const [prog, setProg] = useState<[number, number] | null>(null);
  const [err, setErr] = useState(false);
  const busy = prog != null;
  const run = async () => {
    setErr(false);
    setProg([0, 1]);
    const r = await saveCantonOffline(id, name, (d, t) => setProg([d, t]));
    setProg(null);
    if (r.failed === r.total) setErr(true);
  };
  const label = busy ? `Guardando… ${Math.round((prog![0] / prog![1]) * 100)} %` : saved ? "Actualizar copia" : "Guardar sin conexión";
  return (
    <span className="inline-flex flex-col gap-1">
      <Button variant="outlined" icon={busy ? "hourglass_top" : saved ? "offline_pin" : "download_for_offline"} onClick={run} disabled={busy || !online}
        aria-describedby={`off-${id}`} title={online ? "Descarga los datos de este cantón para verlos sin señal" : "Necesita conexión para guardar"}>
        {label}
      </Button>
      <span id={`off-${id}`} className="text-xs text-on-surface-muted" aria-live="polite">
        {err ? <span className="text-error">No se pudo guardar. Revise la conexión.</span> : saved ? `Disponible sin conexión · ${fmtDate(saved.savedAt)}` : null}
      </span>
    </span>
  );
}
