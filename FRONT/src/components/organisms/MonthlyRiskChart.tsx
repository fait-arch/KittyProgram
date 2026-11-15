"use client";
import dynamic from "next/dynamic";
import type { MonthlyRisk } from "@/lib/api/types";
import { baseOption, useChartTokens } from "@/lib/charts/tokens";
import { fmt2, MONTHS_NAME } from "@/lib/design/format";
import { ChartFrame, ChartTable } from "@/components/molecules/ChartFrame";
import { Skeleton } from "@/components/atoms/Skeleton";
import { EmptyCacao } from "@/components/atoms/Anim";

const EChart = dynamic(() => import("@/components/atoms/EChart").then((m) => m.EChart), { ssr: false, loading: () => <Skeleton className="h-[220px]" /> });

/**
 * Organismo · riesgo mensual por patógeno (0–1). Líneas con área suave, época de lluvias
 * sombreada, cruz + tooltip al pasar el cursor, marca del mes más riesgoso.
 */
export function MonthlyRiskChart({ data }: { data: MonthlyRisk[] }) {
  const t = useChartTokens();
  const b = baseOption(t);
  // La base puede no tener riesgo mensual para un cantón o escenario: se avisa en vez de romper la ficha
  if (!data?.length) {
    return (
      <section aria-label="Riesgo mensual" className="rounded-lg bg-surface-high p-5">
        <EmptyCacao title="Sin riesgo mensual para este escenario">
          Todavía no hay índice de riesgo de enfermedad mes a mes para este cantón en este escenario.
        </EmptyCacao>
      </section>
    );
  }
  const peak = data.reduce((a, x) => (x.monilia > a.monilia ? x : a), data[0]);
  const series = (name: string, key: "monilia" | "phytophthora", color: string) => ({
    name, type: "line" as const, smooth: 0.35, symbol: "circle", symbolSize: 8, showSymbol: false,
    lineStyle: { width: 2, color }, itemStyle: { color, borderColor: t.surface, borderWidth: 2 },
    emphasis: { disabled: true },
    areaStyle: { color: { type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + "55" }, { offset: 1, color: color + "00" }] } },
    data: data.map((m) => m[key]),
  });
  const option = {
    ...b,
    grid: { ...b.grid, top: 28 },
    tooltip: {
      ...b.tooltip, trigger: "axis" as const,
      axisPointer: { type: "line" as const, lineStyle: { color: t.outline, type: "dashed" as const } },
      valueFormatter: (v: unknown) => fmt2(Number(v)),
    },
    xAxis: { type: "category" as const, data: MONTHS_NAME, boundaryGap: false, ...b.axisCommon, splitLine: { show: false } },
    yAxis: { type: "value" as const, min: 0, max: 1, interval: 0.25, ...b.axisCommon, axisLine: { show: false },
      axisLabel: { ...b.axisCommon.axisLabel, formatter: (v: number) => (v === 0 || v === 1 ? String(v) : fmt2(v)) } },
    series: [
      {
        ...series("Moniliasis", "monilia", t["series-monilia"]),
        markArea: { silent: true, itemStyle: { color: t.primary, opacity: 0.08 }, label: { color: t["on-surface-variant"], fontSize: 11, position: "insideTopLeft" as const },
          data: [[{ name: "Lluvias ene–jun", xAxis: "Ene" }, { xAxis: "Jun" }]] },
        markLine: { silent: true, symbol: "none", lineStyle: { color: t["series-monilia"], type: "dotted" as const },
          label: { formatter: `Pico · ${MONTHS_NAME[peak.month - 1]}`, color: t["on-surface"], fontSize: 11, position: "end" as const },
          data: [{ xAxis: MONTHS_NAME[peak.month - 1] }] },
      },
      series("Mazorca negra", "phytophthora", t["series-phyto"]),
    ],
  };
  return (
    <ChartFrame
      title="Riesgo mes a mes"
      subtitle="Índice de clima favorable a la enfermedad (0 = nada, 1 = máximo)"
      legend={[{ label: "Moniliasis", color: t["series-monilia"] }, { label: "Mazorca negra", color: t["series-phyto"] }]}
      table={<ChartTable caption="Riesgo mensual por enfermedad" head={["Mes", "Moniliasis", "Mazorca negra"]}
        rows={data.map((m) => [MONTHS_NAME[m.month - 1], fmt2(m.monilia), fmt2(m.phytophthora)])} />}
    >
      <EChart option={option} height={220}
        label={`Riesgo mensual; el mayor riesgo de moniliasis es en ${MONTHS_NAME[peak.month - 1]} (${fmt2(peak.monilia)}).`} />
    </ChartFrame>
  );
}
