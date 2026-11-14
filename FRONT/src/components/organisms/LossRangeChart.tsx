"use client";
import dynamic from "next/dynamic";
import type { CompareItem, Scenario } from "@/lib/api/types";
import { baseOption, useChartTokens } from "@/lib/charts/tokens";
import { lossClassIndex, RISK_BREAKS, RISK_CLASSES, RISK_LABEL } from "@/lib/design/colors";
import { fmtPct, fmtPctRange } from "@/lib/design/format";
import { ChartTable } from "@/components/molecules/ChartFrame";
import { Skeleton } from "@/components/atoms/Skeleton";

const EChart = dynamic(() => import("@/components/atoms/EChart").then((m) => m.EChart), { ssr: false, loading: () => <Skeleton className="h-[260px]" /> });

/**
 * Organismo · estimación central + rango p10–p90 por escenario.
 * Fondo con las franjas de la alerta de 5 niveles; el punto toma el color de su nivel.
 */
export function LossRangeChart({ items, scenarios, asTable }: { items: CompareItem[]; scenarios?: Scenario[]; asTable?: boolean }) {
  const t = useChartTokens();
  const b = baseOption(t);
  const label = (id: string) => scenarios?.find((s) => s.id === id)?.label ?? id;
  if (asTable) {
    return <ChartTable caption="Pérdida por escenario" head={["Escenario", "Pérdida", "Rango p10–p90", "Nivel"]}
      rows={items.map((i) => [label(i.scenario), fmtPct(i.loss.loss_pct), fmtPctRange(i.loss.loss_pct_low, i.loss.loss_pct_high), RISK_LABEL[i.loss.risk_class]])} />;
  }
  const max = Math.max(60, Math.ceil(Math.max(...items.map((i) => i.loss.loss_pct_high)) / 10) * 10);
  const levelColor = (v: number) => t[`loss-${lossClassIndex(v)}` as "loss-0"];
  const bands = [0, ...RISK_BREAKS, max].slice(0, -1).map((lo, k) => [
    { yAxis: lo, name: RISK_LABEL[RISK_CLASSES[k]], itemStyle: { color: t[`loss-${k}` as "loss-0"], opacity: 0.1 } },
    { yAxis: k < 4 ? RISK_BREAKS[k] : max },
  ]);
  const option = {
    ...b,
    grid: { ...b.grid, right: 88, top: 12 },
    tooltip: {
      ...b.tooltip, trigger: "item" as const,
      formatter: (p: { dataIndex: number }) => {
        const i = items[p.dataIndex];
        return `<b>${label(i.scenario)}</b><br/>Pérdida ${fmtPct(i.loss.loss_pct)} · ${RISK_LABEL[i.loss.risk_class]}<br/>Rango probable ${fmtPctRange(i.loss.loss_pct_low, i.loss.loss_pct_high)}${i.extrapolation ? "<br/><i>Extrapolación</i>" : ""}`;
      },
    },
    xAxis: { type: "category" as const, data: items.map((i) => label(i.scenario)), ...b.axisCommon, splitLine: { show: false },
      axisLabel: { ...b.axisCommon.axisLabel, color: t["on-surface-variant"], fontSize: 12, interval: 0, width: 90, overflow: "break" as const } },
    yAxis: { type: "value" as const, min: 0, max, interval: 15, ...b.axisCommon, axisLine: { show: false },
      axisLabel: { ...b.axisCommon.axisLabel, formatter: "{value} %" } },
    series: [
      {
        type: "custom" as const, name: "Rango p10–p90", silent: true,
        data: items.map((i, k) => [k, i.loss.loss_pct_low, i.loss.loss_pct_high]),
        renderItem: (_: unknown, api: { value: (d: number) => number; coord: (p: number[]) => number[] }) => {
          const x = api.value(0), lo = api.coord([x, api.value(1)]), hi = api.coord([x, api.value(2)]);
          const style = { stroke: t["on-surface-variant"], lineWidth: 2 };
          return { type: "group", children: [
            { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style },
            { type: "line", shape: { x1: lo[0] - 7, y1: lo[1], x2: lo[0] + 7, y2: lo[1] }, style },
            { type: "line", shape: { x1: hi[0] - 7, y1: hi[1], x2: hi[0] + 7, y2: hi[1] }, style },
          ] };
        },
        markArea: { silent: true, label: { show: true, position: "right" as const, color: t["on-surface-muted"], fontSize: 11, distance: 4 }, data: bands },
        z: 2,
      },
      {
        type: "scatter" as const, name: "Estimación central", symbolSize: 18, z: 3,
        data: items.map((i) => ({ value: i.loss.loss_pct, itemStyle: { color: levelColor(i.loss.loss_pct), borderColor: t["loss-outline"], borderWidth: 1.5, shadowBlur: 0 } })),
        emphasis: { scale: 1.25, itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,.4)" } },
        label: { show: true, position: "right" as const, distance: 10, color: t["on-surface"], fontFamily: t.display, fontWeight: 800, fontSize: 15,
          formatter: (p: { value: number }) => fmtPct(p.value) },
      },
    ],
  };
  return <EChart option={option} height={280} label={items.map((i) => `${label(i.scenario)}: ${fmtPct(i.loss.loss_pct)}, rango ${fmtPctRange(i.loss.loss_pct_low, i.loss.loss_pct_high)}`).join("; ")} />;
}
