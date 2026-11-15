/** Formato de cifras en español de Ecuador: 41.000 t · USD 4,9 M · 22,4 % */
const nf0 = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("es-EC", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtInt = (v: number) => nf0.format(v);
export const fmt1 = (v: number) => nf1.format(v);
export const fmt2 = (v: number) => nf2.format(v);
export const fmtPct = (v: number) => `${nf1.format(v)} %`;
export const fmtPctRange = (lo: number, hi: number) => `${nf0.format(lo)} – ${nf0.format(hi)} %`;
export const fmtPts = (v: number) => `${v >= 0 ? "+" : "−"}${nf1.format(Math.abs(v))} pts`;
export const fmtSigned = (v: number) => `${v >= 0 ? "+" : "−"}${nf2.format(Math.abs(v))}`;

/** Toneladas redondeadas a la decena: 1.830 t */
export const fmtT = (v: number | null | undefined) => (v == null ? "—" : `${nf0.format(Math.round(v / 10) * 10)} t`);

/** USD compacto: USD 4,9 M · USD 110 M · USD 850 mil */
export function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e8) return `USD ${nf0.format(v / 1e6)} M`;
  if (a >= 1e6) return `USD ${nf1.format(v / 1e6)} M`;
  if (a >= 1e3) return `USD ${nf0.format(v / 1e3)} mil`;
  return `USD ${nf0.format(v)}`;
}

export const MONTHS_SHORT = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
export const MONTHS_NAME = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/** «6,3 pts» o «sin dato» si el backend aún no tiene un modelo entrenado */
export const fmtMae = (v: number | null | undefined) => (v == null ? "sin dato" : `${(Math.round(v * 10) / 10).toFixed(1).replace(".", ",")} pts`);
/** «+1.230 t» / «−1.230 t» frente a otro escenario */
export const fmtDeltaT = (v: number) => `${v >= 0 ? "+" : "−"}${fmtT(Math.abs(v))}`;
export const fmtDeltaUsd = (v: number) => `${v >= 0 ? "+" : "−"}${fmtUsd(Math.abs(v))}`;
/** «2002–2024» o «sin dato» */
export const fmtYears = (y: [number | null, number | null]) => (y[0] == null || y[1] == null ? "sin dato" : `${y[0]}–${y[1]}`);
