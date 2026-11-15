"use client";
import type { Meta } from "@/lib/api/types";
import { useEnso, useMeta } from "@/lib/api/hooks";
import { fmtMae, fmtYears } from "@/lib/design/format";
import { fmt2 } from "@/lib/design/format";
import { useTheme } from "@/lib/theme";
import { Icon } from "@/components/atoms/Icon";
import { AlertScale } from "@/components/organisms/AlertScale";

/** Pantalla · metodología, fuentes, métricas del modelo y explicación de El Niño (GET /meta, /enso/current). */
export function MethodologyScreen() {
  const { data: meta } = useMeta();
  const { data: enso } = useEnso();
  const { theme } = useTheme();
  return (
    <div className="mx-auto flex max-w-[960px] flex-col gap-10 px-4 py-8 lg:px-8">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Metodología</span>
        <h1 className="font-display text-[32px] leading-10 font-extrabold">¿Cómo se calcula la pérdida?</h1>
        <p className="text-base leading-6 text-on-surface-variant">
          Cruzamos lo que necesita el cacao (ECOCROP) con un índice de clima favorable a enfermedades hecho con datos de la NASA,
          entrenamos un modelo con la producción real (ESPAC/INEC) y El Niño (NOAA), y estimamos la pérdida por cantón en toneladas y dólares.
        </p>
      </header>

      <section id="enso" className="flex scroll-mt-4 flex-col gap-3 rounded-lg bg-surface-high p-6">
        <h2 className="flex items-center gap-2 font-display text-xl font-bold"><Icon name="waves" className="text-primary" />¿Qué significa El Niño para mi cacao?</h2>
        <p className="leading-6">
          Cuando el mar frente a Ecuador se calienta (región Niño 1+2), llueve más y hay más días húmedos en la Costa. Eso dispara la
          moniliasis y la mazorca negra, lava las flores y encharca el suelo.
          {enso && enso.phase === "nino" && (
            <> Hoy el índice ONI está en <b>{enso.oni.value >= 0 ? "+" : ""}{fmt2(enso.oni.value)}</b> y la anomalía de Niño 1+2 en <b>{enso.nino12.anomaly_c >= 0 ? "+" : ""}{fmt2(enso.nino12.anomaly_c)} °C</b> ({enso.source}).</>
          )}
        </p>
        <p className="text-sm text-on-surface-variant">Los umbrales de enfermedad son referenciales de literatura y deben validarse con INIAP o un fitopatólogo.</p>
      </section>

      <AlertScale theme={theme} />

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-xl font-bold">Fuentes de datos</h2>
        <div className="overflow-x-auto rounded-lg border border-outline-variant">
          <table className="w-full text-sm">
            <thead className="bg-surface-high text-left text-xs uppercase tracking-wide text-on-surface-variant">
              <tr><th className="px-4 py-2">Fuente</th><th className="px-4 py-2">Proveedor</th><th className="px-4 py-2">Para qué</th></tr>
            </thead>
            <tbody>
              {meta?.sources.map((s) => (
                <tr key={s.id} className="border-t border-outline-variant">
                  <td className="px-4 py-2 font-semibold">{s.name}</td>
                  <td className="px-4 py-2">{s.provider}</td>
                  <td className="px-4 py-2 text-on-surface-variant">{s.use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {meta && (
        <section className="flex flex-col gap-3">
          <h2 className="font-display text-xl font-bold">Modelo y validación</h2>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["Modelo", meta.model.name],
              ["Error medio (MAE)", fmtMae(meta.model.mae)],
              ["Mejora vs línea base", meta.model.skill_vs_baseline == null ? "sin dato" : `${Math.round(meta.model.skill_vs_baseline * 100)} %`],
              ["Cobertura del rango p10–p90", meta.model.interval_coverage == null ? "sin dato" : `${Math.round(meta.model.interval_coverage * 100)} %`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-md bg-surface-high p-4">
                <span className="block text-xs text-on-surface-variant">{k}</span>
                <span className="font-display text-lg font-extrabold">{v}</span>
              </div>
            ))}
          </div>
          <p className="text-sm text-on-surface-variant">
            {meta.model.note && <><b>{meta.model.note}</b>{" "}</>}
            Validación «dejando un año fuera» ({fmtYears(meta.model.trained_years)}): se entrena sin una temporada y se predice esa temporada.
            Para 2050 el modelo se aplica fuera del clima con que se entrenó; se muestra como extrapolación.
          </p>
          {meta.model.validation && <Validation v={meta.model.validation} algorithm={meta.model.algorithm} n={meta.model.n_samples} />}
        </section>
      )}

      <section className="flex gap-3 rounded-lg border border-outline-variant p-5">
        <Icon name="info" className="text-primary" />
        <p className="text-sm leading-6">
          <b>Apoya, no reemplaza, al técnico.</b> Las cifras son estimaciones con datos satelitales y estadísticos; antes de invertir, valide con INIAP o MAG.
        </p>
      </section>
    </div>
  );
}

const f2 = (v: number | null) => (v == null ? "—" : v.toFixed(2).replace(".", ","));
const pv = (v: number | null) => (v == null ? "—" : v < 0.001 ? "< 0,001" : v.toFixed(3).replace(".", ","));

/** Validación del modelo de ML (ficha model_version_v1): sin ver el año que predice. */
function Validation({ v, algorithm, n }: { v: NonNullable<Meta["model"]["validation"]>; algorithm?: string | null; n?: number | null }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-outline-variant p-4">
          <b className="text-sm">Nacional · validado</b>
          <p className="mt-1 text-[15px] leading-[22px]">Correlación <b>{f2(v.corr)}</b> · R² <b>{f2(v.r2)}</b> · prueba de permutación p = <b>{pv(v.p)}</b>.</p>
          {!!v.nino_years_hit.length && <p className="mt-1 text-[13px] text-on-surface-variant">Anticipó los años Niño {v.nino_years_hit.join(", ")} sin haberlos visto en el entrenamiento.</p>}
        </div>
        <div className="rounded-lg border border-outline-variant p-4">
          <b className="text-sm">Provincias y cantones · índice de riesgo</b>
          <p className="mt-1 text-[15px] leading-[22px]">R² <b>{f2(v.province_corr)}</b> · p = <b>{pv(v.province_p)}</b> (significativo, pero débil). Por zona es un índice, no una predicción exacta: el mapa lo marca como «Estimación por zona».</p>
        </div>
      </div>
      <ul className="list-disc pl-5 text-sm leading-[21px] text-on-surface-variant">
        <li>Algoritmo: {algorithm ?? "—"}{n ? `, ${n} años-área de entrenamiento` : ""}. Se valida «dejando un año fuera»: nunca ve el año que predice.</li>
        <li>La señal fuerte viene de los Niños costeros extremos (1983, 1998). Un «año Niño» por el índice ONI casi no trajo lluvia extrema a la Costa.</li>
        <li>Los umbrales de enfermedad no están validados por el INIAP: los resultados deben revisarse con técnicos.</li>
        <li>Fuentes: NASA (GPM IMERG, MODIS EVI, SMAP, GLDAS, SRTM), ERA5-Land (Copernicus), NOAA CPC, FAOSTAT e INEC-ESPAC.</li>
      </ul>
    </div>
  );
}
