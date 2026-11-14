"use client";
import Link from "next/link";
import { useEnso } from "@/lib/api/hooks";
import { Icon } from "@/components/atoms/Icon";

const SEASON: Record<string, string> = {
  DJF: "dic–feb", JFM: "ene–mar", FMA: "feb–abr", MAM: "mar–may", AMJ: "abr–jun", MJJ: "may–jul",
  JJA: "jun–ago", JAS: "jul–sep", ASO: "ago–oct", SON: "sep–nov", OND: "oct–dic", NDJ: "nov–ene",
};
const MONTH = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const STRENGTH: Record<string, string> = { debil: "débil", moderado: "moderado", fuerte: "fuerte", muy_fuerte: "muy fuerte" };
const signed = (v: number, d = 2) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d).replace(".", ",")}`;

/** Banner M3 con la fase ENSO vigente (GET /enso/current). Siempre visible. */
export function EnsoBanner() {
  const { data } = useEnso();
  if (!data) return <div className="h-12 bg-surface" aria-hidden />;
  const nino = data.phase === "nino";
  const title = nino
    ? `El Niño ${STRENGTH[data.strength ?? ""] ?? ""} ${data.event_in_progress ? "en curso" : ""}`
    : data.phase === "nina" ? "La Niña en curso" : "ENSO neutro";
  const [y, m] = data.nino12.month.split("-");
  return (
    <section
      id="enso"
      aria-label="Estado de El Niño"
      className="flex flex-wrap items-center gap-x-5 gap-y-2 bg-linear-to-br from-banner-from to-banner-to px-4 py-2.5 text-on-banner lg:px-6 no-print"
    >
      <Icon name={nino ? "warning" : "waves"} fill size={26} className={nino ? "text-neon-yellow" : "text-primary"} />
      <span className="font-display text-[15px] font-black uppercase tracking-wider">{title.replace(/\s+/g, " ").trim()}</span>
      <span className="hidden items-baseline gap-2 rounded-sm border border-on-banner-variant/40 px-3 py-0.5 text-[13px] text-on-banner-variant sm:inline-flex">
        ONI {SEASON[data.oni.season] ?? data.oni.season} {data.oni.year}
        <b className="font-display text-base text-white tabular">{signed(data.oni.value)}</b>
      </span>
      <span className="hidden items-baseline gap-2 rounded-sm border border-on-banner-variant/40 px-3 py-0.5 text-[13px] text-on-banner-variant md:inline-flex">
        Niño 1+2 {MONTH[Number(m) - 1]} {y}
        <b className="font-display text-base text-white tabular">{signed(data.nino12.anomaly_c)} °C</b>
      </span>
      <span className="hidden text-xs text-white/70 lg:inline">Fuente: {data.source}</span>
      <span className="flex-1" />
      <Link href="/metodologia#enso" className="inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-bold text-neon-yellow hover:bg-white/10">
        ¿Qué significa para mi cacao?
        <Icon name="arrow_forward" size={18} />
      </Link>
    </section>
  );
}
