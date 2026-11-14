"use client";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

/** Botón segmentado M3, selección única. Se usa para el escenario (estado global de la app). */
export function SegmentedButton<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: { value: T; label: string; disabled?: boolean }[];
  value: T | null;
  onChange: (v: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cn("flex h-10 gap-px overflow-hidden rounded-full border border-outline bg-outline", className)}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex flex-1 basis-0 items-center justify-center gap-1 whitespace-nowrap px-2 text-sm font-semibold cursor-pointer disabled:opacity-40",
              on ? "bg-secondary-container text-on-secondary-container" : "bg-surface text-on-surface hover:bg-surface-high",
            )}
          >
            {on && <Icon name="check" size={18} />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
