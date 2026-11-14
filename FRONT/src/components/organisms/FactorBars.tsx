"use client";
import dynamic from "next/dynamic";
import type { Factor } from "@/lib/api/types";
import { baseOption, useChartTokens } from "@/lib/charts/tokens";
import { fmt1, fmtInt } from "@/lib/design/format";
import { ChartFrame, ChartTable } from "@/components/molecules/ChartFrame";
import { Skeleton } from "@/components/atoms/Skeleton";

const EChart = dynamic(() => import("@/components/atoms/EChart").then((m) => m.EChart), { ssr: false, loading: () => <Skeleton className="h-40" /> });

/** Organismo · "¿Por qué?": contribución de cada factor (SHAP) en barras horizontales de un solo tono. */
export function FactorBars({ factors }: { factors: Factor[] }) {
  const t = useChartTokens();
  const b = baseOption(t);
  const rows = [...factors].sort((a, z) => a.contribution_pct - z.contribution_pct); // ECharts dibuja de abajo hacia arriba
  const option = {
    ...b,
    grid: { left: 4, right: 72, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      ...b.tooltip, trigger: "item" as const,
      formatter: (p: { dataIndex: number }) => {
        const f = rows[p.dataIndex];
        return `<b>${f.label}</b><br/>+${fmt1(f.contribution_pct)} puntos de pérdida<br/><span style="opacity:.75">${fmtInt(f.value)} ${f.unit} · ${f.source}</span>`;
      },
    },
    xAxis: { type: "value" as const, show: false },
    yAxis: { type: "category" as const, data: rows.map((f) => f.label), axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: t["on-surface"], fontSize: 13, width: 200, overflow: "break" as const, lineHeight: 16 } },
    series: [{
      type: "bar" as const, barWidth: 12, data: rows.map((f) => f.contribution_pct),
      itemStyle: { color: t.primary, borderRadius: [0, 4, 4, 0] },
      showBackground: true, backgroundStyle: { color: t["surface-high"], borderRadius: [0, 4, 4, 0] },
      emphasis: { itemStyle: { color: t.primary, shadowBlur: 8, shadowColor: t.primary + "66" } },
      label: { show: true, position: "right" as const, color: t["on-surface"], fontFamily: t.display, fontWeight: 800, fontSize: 14,
        formatter: (p: { value: number }) => `+${fmt1(p.value)} pts` },
    }],
  };
  return (
    <ChartFrame
      title="¿Por qué?"
      subtitle="Lo que más suma a la pérdida, en puntos porcentuales"
      table={<ChartTable caption="Contribución de cada factor a la pérdida" head={["Factor", "Puntos", "Valor", "Fuente"]}
        rows={factors.map((f) => [f.label, `+${fmt1(f.contribution_pct)}`, `${fmtInt(f.value)} ${f.unit}`, f.source])} />}
    >
      <EChart option={option} height={Math.max(120, factors.length * 52)}
        label={factors.map((f) => `${f.label}: +${fmt1(f.contribution_pct)} puntos`).join("; ")} />
      <span className="text-xs text-on-surface-muted">Contribuciones del modelo (SHAP). Pase el cursor para ver el dato y la fuente.</span>
    </ChartFrame>
  );
}
