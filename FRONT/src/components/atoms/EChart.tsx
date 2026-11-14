"use client";
/**
 * Átomo · lienzo de ECharts (Apache-2.0) con importación por partes (solo lo que se usa).
 * Se carga del lado del cliente; el resto de la página no espera a la librería.
 */
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, CustomChart, LineChart, ScatterChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

echarts.use([BarChart, LineChart, ScatterChart, CustomChart, GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, AriaComponent, CanvasRenderer]);

export function EChart({ option, height = 220, label, onEvents }: {
  /** Opciones de ECharts (se tipan aquí como objeto: los callbacks de formato rompen los tipos estrictos) */
  option: object;
  height?: number;
  /** Descripción para lectores de pantalla (además de la tabla equivalente) */
  label: string;
  onEvents?: Record<string, (p: unknown) => void>;
}) {
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ReactEChartsCore
        echarts={echarts}
        option={{ aria: { enabled: true, label: { description: label } }, ...stripLocal(option) } as EChartsOption}
        notMerge
        lazyUpdate
        style={{ height: "100%", width: "100%" }}
        opts={{ renderer: "canvas" }}
        onEvents={onEvents}
      />
    </div>
  );
}

/** Quita claves propias (axisCommon) que no son opciones de ECharts */
function stripLocal(o: object): Record<string, unknown> {
  const { axisCommon: _drop, ...rest } = o as Record<string, unknown>;
  void _drop;
  return rest;
}
