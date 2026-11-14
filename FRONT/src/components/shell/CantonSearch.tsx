"use client";
import { useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAreas } from "@/lib/api/hooks";
import { Icon } from "@/components/ui/Icon";

/** Barra de búsqueda M3: escribe un cantón y abre su panel en el mapa. */
export function CantonSearch() {
  const { data: areas } = useAreas("canton");
  const [q, setQ] = useState("");
  const router = useRouter();
  const sp = useSearchParams();
  const listId = useId();

  function go(text: string) {
    const t = text.trim().toLowerCase();
    const hit = areas?.find((a) => `${a.name} · ${a.province}`.toLowerCase() === t) ?? areas?.find((a) => a.name.toLowerCase() === t);
    if (!hit) return;
    const next = new URLSearchParams(sp.toString());
    next.set("canton", hit.id);
    router.push(`/?${next.toString()}`);
    setQ("");
  }

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        go(q);
      }}
      className="flex h-12 w-full max-w-[560px] items-center gap-3 rounded-full bg-surface-high px-4 text-on-surface-variant"
    >
      <Icon name="search" />
      <label htmlFor={`${listId}-in`} className="sr-only">Buscar cantón</label>
      <input
        id={`${listId}-in`}
        type="search"
        list={listId}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          if (areas?.some((a) => `${a.name} · ${a.province}` === e.target.value)) go(e.target.value);
        }}
        placeholder="Buscar cantón"
        className="min-w-0 flex-1 bg-transparent text-base text-on-surface outline-none placeholder:text-on-surface-variant"
      />
      <datalist id={listId}>
        {areas?.map((a) => <option key={a.id} value={`${a.name} · ${a.province}`} />)}
      </datalist>
    </form>
  );
}
