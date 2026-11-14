"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { IconButton } from "./Button";

/** Diálogo M3 sobre <dialog> nativo (foco atrapado, Esc para cerrar). */
export function Dialog({ open, onClose, title, icon, children, footer, className }: {
  open: boolean;
  onClose: () => void;
  title: string;
  icon?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-label={title}
      className={cn(
        "m-auto w-[min(920px,calc(100vw-24px))] max-h-[calc(100dvh-24px)] rounded-xl bg-surface-high p-0 text-on-surface shadow-2xl backdrop:bg-black/60",
        className,
      )}
    >
      {open && (
        <div className="flex max-h-[calc(100dvh-24px)] flex-col">
          <header className="flex items-center gap-3 px-6 pt-5 pb-2">
            {icon && <span className="ms text-primary" aria-hidden>{icon}</span>}
            <h2 className="flex-1 font-display text-2xl font-extrabold">{title}</h2>
            <IconButton icon="close" label="Cerrar" onClick={onClose} />
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-4">{children}</div>
          {footer && <footer className="flex flex-wrap items-center gap-3 border-t border-outline-variant px-6 py-4">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}
