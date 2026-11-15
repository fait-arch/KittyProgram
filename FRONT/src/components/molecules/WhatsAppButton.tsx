"use client";
import { cn } from "@/lib/cn";
import { useUltimaConsulta, waLink, WA_DISPLAY, type Consulta } from "@/lib/whatsapp";
import { Icon } from "@/components/atoms/Icon";

/**
 * Molécula · botón de asesoría por WhatsApp.
 * - Sin `consulta`: usa la última consulta guardada (ficha de cantón o alerta); si no hay, mensaje genérico.
 * - `variant="bar"` para la barra superior; `"block"` dentro de fichas y alertas.
 */
export function WhatsAppButton({ consulta, variant = "block", label, className }: {
  consulta?: Consulta | null;
  variant?: "bar" | "block";
  label?: string;
  className?: string;
}) {
  const last = useUltimaConsulta();
  const c = consulta === undefined ? last : consulta;
  const text = label ?? (c ? "Hablar con un asesor sobre esto" : "Asesoría por WhatsApp");
  return (
    <a
      href={waLink(c)}
      target="_blank"
      rel="noopener noreferrer"
      title={c ? `Abre WhatsApp (${WA_DISPLAY}) con su consulta de ${c.nombre}` : `Abre WhatsApp (${WA_DISPLAY})`}
      className={cn(
        "state-layer inline-flex items-center gap-2 rounded-full font-semibold text-[#052e16] bg-[#25d366] hover:bg-[#2fe072] focus-visible:outline-2 focus-visible:outline-offset-2",
        variant === "bar" ? "h-10 px-4 text-sm" : "h-11 px-5 text-[15px] self-start",
        className,
      )}
    >
      <Icon name="chat" fill size={20} />
      <span className={variant === "bar" ? "hidden lg:inline" : undefined}>{variant === "bar" ? (c ? "Asesor · tu consulta" : "Asesoría") : text}</span>
      <span className="sr-only">(WhatsApp {WA_DISPLAY})</span>
    </a>
  );
}
