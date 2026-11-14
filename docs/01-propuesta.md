# 1. Propuesta — CacaoResiliente

> Reto: **Field Shift: Adapting Farms with NASA Data** — NASA Space Apps Challenge 2026.

**Producto:** cacao (*Theobroma cacao*) — Nacional fino de aroma y CCN-51 — en la Costa del Ecuador.

## Problema

El Niño trae lluvias extremas y humedad que disparan la moniliasis y la mazorca negra en el
cacao, y el cambio climático está sacando zonas del rango óptimo del cultivo (21–32 °C,
1 200–3 000 mm/año); el productor pierde cosechas e invierte a más de 25 años sin saber
cuánto arriesga ni dónde.

## Pregunta

> **¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades
> asociadas a El Niño, hoy y con el clima de 2050?**

## Solución

Una herramienta web que, con datos NASA (GPM, SMAP, SRTM, MODIS, NEX-GDDP-CMIP6) y ERA5:

1. Cruza los **requerimientos del cacao** (ECOCROP) con un **índice de clima favorable a
   enfermedades fúngicas** (días cálidos y húmedos, lluvia extrema, suelo saturado).
2. Usa un **modelo predictivo** entrenado con la producción real (ESPAC/INEC, FAOSTAT) y
   el historial de El Niño (NOAA) para **estimar la pérdida por cantón** (t y USD) en un año
   normal, en un año Niño y en 2050.
3. **Recomienda la estrategia** de manejo que más reduce esa pérdida en cada zona,
   explicando evidencia, incertidumbre y qué debe validar un técnico.

## Por qué ahora

Los datos de NOAA CPC muestran un **El Niño fuerte en curso**: ONI ASO-2026 = **+2.46** y
anomalía de temperatura del mar en la región Niño 1+2 (frente a Ecuador) de **+5.25 °C** en
octubre de 2026. La herramienta responde una pregunta urgente para esta temporada.

## Requerimientos del cacao (ECOCROP, `OpenCLIM/ecocrop`)

| Parámetro | Óptimo | Absoluto |
|-----------|--------|----------|
| Temperatura media | 21 – 32 °C | 10 – 38 °C |
| Lluvia anual | 1 200 – 3 000 mm | 900 – 7 600 mm |
| pH del suelo | 5.0 – 6.5 | — |
| Altitud máxima | 900 m | — |
| Luz | Cielo despejado a sombra ligera | — |
| Suelo | Profundo (>150 cm), pesado/orgánico, bien drenado | — |
| Ciclo | 180 – 365 días | — |

## Qué pasa con mucha humedad y lluvia

| Efecto | Mecanismo | Variable que lo mide |
|--------|-----------|----------------------|
| Moniliasis (*Moniliophthora roreri*) | Esporas se dispersan y germinan con humedad alta sostenida | Días con HR alta y T en rango (ERA5-Land) |
| Mazorca negra (*Phytophthora* spp.) | Lluvia salpica esporas; suelo y mazorca mojados | Lluvia diaria y días lluviosos (GPM) |
| Escoba de bruja (*M. perniciosa*) | Humedad y brotes tiernos | HR + temperatura |
| Asfixia radicular | Suelo saturado varios días | Humedad del suelo (SMAP), zonas bajas (SRTM) |
| Menos cuajado | Lluvia intensa lava flores | Días de lluvia > 50 mm (GPM) |
| Calidad poscosecha | Secado y fermentación deficientes | Días lluviosos en meses de cosecha |

> Los umbrales de enfermedad usados son **referenciales de literatura** y deben validarse con
> INIAP o un fitopatólogo. La app lo indica explícitamente.

## Objetivos

**General:** estimar la pérdida potencial de cacao por enfermedades asociadas a El Niño y la
aptitud climática futura del cultivo, para recomendar estrategias de adaptación por zona.

**Específicos:**

1. Mapear la zona cacaotera y su aptitud actual con ECOCROP.
2. Construir un índice climático mensual de riesgo de enfermedad por cantón.
3. Entrenar un modelo que relacione clima + El Niño con la caída de rendimiento.
4. Estimar la pérdida (t y USD) por cantón en año normal vs año Niño — **Fase 1**.
5. Proyectar aptitud, riesgo y pérdida a 2041–2060 con NEX-GDDP-CMIP6 — **Fase 2**.
6. Comparar ≥ 3 estrategias de adaptación por zona con su evidencia y riesgos.

## Estrategias que compara la herramienta

| # | Estrategia | Reduce |
|---|-----------|--------|
| 0 | Manejo actual (línea base) | — |
| 1 | Manejo sanitario: cosecha sanitaria semanal, poda, retiro de mazorcas enfermas | Moniliasis, mazorca negra |
| 2 | Drenaje + sombra regulada (agroforestería) | Encharcamiento, estrés térmico |
| 3 | Diversificación: cacao + plátano/maderables; rotación de cultivos intercalados en cacao joven | Pérdida total de ingreso |

## Alcance por fases

| Fase | Responde | Si no terminamos… |
|------|----------|-------------------|
| **1** | ¿Cuánto se pierde **hoy** con El Niño vs un año normal? | Ya es un producto completo |
| **2** | ¿Y con el clima de **2050**? + matriz de zonas | Se presenta como trabajo futuro |
| 3 | Finca individual, observaciones de campo, ECOSTRESS | Extra |

Detalle en [06-fases.md](06-fases.md).
