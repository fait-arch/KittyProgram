"use client";
import dynamic from "next/dynamic";
import { useLossSummary } from "@/lib/api/hooks";
import type { RiskClass, Scenario, ScenarioId } from "@/lib/api/types";
import { baseOption, HATCH_DECAL, useChartTokens } from "@/lib/charts/tokens";
import { RISK_CLASSES, RISK_LABEL, type LossLevel } from "@/lib/design/colors";
import { ChartFrame, ChartTable } from "@/components/molecules/ChartFrame";
import { Skeleton } from "@/components/atoms/Skeleton";
import { Swatch } from "@/components/atoms/Swatch";

const EChart = dynamic(() => import("@/components/atoms/EChart").then((m) => m.EChart), { ssr: false, loading: () => <Skeleton className="h-[240px]" /> });
const IDS: ScenarioId[] = ["normal", "nino", "nino_extremo", "actual"];

/**
 * Organismo · cuántos cantones caen en cada nivel de alerta, por escenario (barras apiladas al 100 %).
 * Muestra de un vistazo cómo El Niño y 2050 corren la Costa hacia el rojo.
 */
export function ClassMixChart({ province, scenarios }: { province?: string; scenarios?: Scenario[] }) {
  const t = useChartTokens();
  const b = baseOption(t);
  const s = [useLossSummary("normal", province), useLossSummary("nino", province), useLossSummary("actual", province), useLossSummary("ssp245_2050", province), useLossSummary("ssp585_2050", province)];
  const label = (id: ScenarioId) => scenarios?.find((x) => x.id === id)?.label ?? id;
  const ready = s.every((x) => x.data);
  const counts = (c: RiskClass) => s.map((x) => x.data?.areas_by_class[c] ?? 0);
  const total = s.map((x) => x.data?.n_areas ?? 1);
  const option = {
    ...b,
    grid: { ...b.grid, top: 4 },
    tooltip: {
      ...b.tooltip, trigger: "axis" as const, axisPointer: { type: "shadow" as const, shadowStyle: { color: t.primary, opacity: 0.08 } },
      formatter: (ps: { dataIndex: number; seriesName: string; value: number; color: string }[]) =>
        `<b>${label(IDS[ps[0].dataIndex])}</b><br/>` + [...ps].reverse().map((p) => `${p.seriesName}: <b>${s[ps[0].dataIndex].data?.areas_by_class[RISK_CLASSES.find((c) => RISK_LABEL[c] === p.seriesName)!]}</b> cantones (${Math.round(p.value)} %)`).join("<br/>"),
    },
    xAxis: { type: "value" as const, max: 100, ...b.axisCommon, axisLabel: { ...b.axisCommon.axisLabel, formatter: "{value} %" } },
    yAxis: { type: "category" as const, inverse: true, data: IDS.map(label), axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: t["on-surface"], fontSize: 13 } },
    series: RISK_CLASSES.map((c, k) => ({
      name: RISK_LABEL[c], type: "bar" as const, stack: "total", barWidth: 22,
      itemStyle: { color: t[`loss-${k}` as "loss-0"], borderColor: t.surface, borderWidth: 1, ...(k === 4 ? { decal: HATCH_DECAL } : {}) },
      emphasis: { focus: "series" as const },
      label: { show: true, color: k >= 3 ? "#ffffff" : "#14261c", fontSize: 11, fontWeight: 700,
        formatter: (p: { dataIndex: number; value: number }) => (p.value >= 7 ? String(counts(c)[p.dataIndex]) : "") },
      data: counts(c).map((n, i) => (n / total[i]) * 100),
    })),
  };
  return (
    <ChartFrame
      title="Cantones en cada nivel de alerta"
      subtitle={`${province ?? "Toda la Costa"} · cada barra suma el 100 % de los cantones`}
      legend={RISK_CLASSES.map((c, k) => ({ label: RISK_LABEL[c], swatch: <Swatch level={k as LossLevel} size="sm" /> }))}
      table={<ChartTable caption="Cantones por nivel de alerta y escenario" head={["Escenario", ...RISK_CLASSES.map((c) => RISK_LABEL[c])]}
        rows={IDS.map((id, i) => [label(id), ...RISK_CLASSES.map((c) => s[i].data?.areas_by_class[c] ?? "—")])} />}
    >
      {ready ? <EChart option={option} height={250} label={IDS.map((id, i) => `${label(id)}: ` + RISK_CLASSES.map((c) => `${RISK_LABEL[c]} ${s[i].data!.areas_by_class[c]}`).join(", ")).join("; ")} />
        : <Skeleton className="h-[250px]" />}
    </ChartFrame>
  );
}
