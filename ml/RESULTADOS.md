# CacaoResiliente — Modelo de pérdida de cacao: qué logramos

> **Pregunta del proyecto** (NASA Space Apps Challenge 2026, reto *Field Shift*):
> *¿Cuánta producción de cacao se perdería en cada zona del Ecuador por enfermedades asociadas
> a El Niño, hoy y con el clima de 2050?*

**En una frase:** con datos de la NASA anticipamos cuánto cacao perdería cada cantón del Ecuador
cuando llega un Niño costero extremo, con un modelo validado estadísticamente, y mostramos que el
riesgo crece hacia 2050 si esos eventos se vuelven más frecuentes.

Este documento explica, en lenguaje claro, qué datos usamos, cómo funciona el modelo, qué tan
bueno es, qué responde y cuáles son sus límites. El detalle técnico está en [`README.md`](README.md),
la ficha completa del modelo en [`artifacts/model_card_v1.json`](artifacts/model_card_v1.json) y
los experimentos en [`experiments/README.md`](experiments/README.md).

---

## Índice

1. [Resumen en números](#1-resumen-en-números)
2. [Los datos](#2-los-datos)
3. [Cómo funciona el modelo](#3-cómo-funciona-el-modelo)
4. [Qué tan bueno es](#4-qué-tan-bueno-es)
5. [Qué responde: escenarios de hoy](#5-qué-responde-escenarios-de-hoy)
6. [2026–2050: el clima futuro](#6-20262050-el-clima-futuro)
7. [Hallazgos principales](#7-hallazgos-principales)
8. [Cómo llegamos aquí: lo que mejoró y lo que no](#8-cómo-llegamos-aquí-lo-que-mejoró-y-lo-que-no)
9. [Límites (lo que hay que decir con honestidad)](#9-límites-lo-que-hay-que-decir-con-honestidad)
10. [Qué se entrega al equipo y cómo se usa](#10-qué-se-entrega-al-equipo-y-cómo-se-usa)
11. [Glosario](#11-glosario)

---

## 1. Resumen en números

| | Resultado |
|---|---|
| Datos | Clima diario **1961–2025** (65 años) · 125 cantones, 7 provincias y el país · producción y exportaciones FAOSTAT, ESPAC por provincia |
| Correlación nacional (fuera de muestra) | **0,64** — al empezar: 0,54 |
| Reducción del error frente a "año normal" | **−23 %** (RMSE 13,9 vs 18,1 puntos) |
| Correlación provincial | **0,32** — al empezar: 0,10 |
| Distingue un año malo de uno bueno | **87 % de las veces** (AUC 0,87) |
| ¿Es casualidad? | **No**: test de permutación p = 0,005 (nacional) y p = 0,01 (provincias) |
| Niños extremos, sin haberlos visto | 1983: **−54 %** (real −50 %) · 1998: **−36 %** (real −64 %) |
| Pérdida en un Niño extremo | **~53 %** de la cosecha nacional |
| Temporada 2027 (Niño costero en curso) | **~21 %**, con riesgo de ser mucho peor |
| Pérdida anual esperada 2050 | **6,4 % hoy → 8,2 %** si los Niños extremos se duplican (+28 %) |
| Ideas probadas para mejorar | **22** (4 adoptadas, 18 descartadas con números) |
| Tests automáticos | **59**, todos pasan |

---

## 2. Los datos

### 2.1 Clima (lo que causa la enfermedad)

| Fuente | Qué aporta | Años |
|---|---|---|
| **ERA5-Land** (Copernicus, vía Google Earth Engine) | Temperatura, humedad, lluvia, suelo, radiación, viento — diario | 1961–2025 |
| **NASA GPM IMERG** | Lluvia medida por satélite: corrige la lluvia de ERA5 | 1998–2025 |
| **WorldClim** (estaciones 1961–1990) | Corrige el sesgo frío de ERA5 en la costa | climatología |
| **NASA MODIS** (EVI/NDVI) | **Verdor de la vegetación** visto desde el satélite | 2000–2025 |
| **NASA GLDAS / SMAP** | Humedad del suelo (comparación) | 2000/2015–2025 |
| **NASA SRTM** | Altitud: solo se mide donde puede haber cacao (< 900 m) | estático |
| **NOAA CPC** | Índices de El Niño (ONI, Niño 1+2, Niño 3.4) | 1950–2026 |
| **NASA NEX-GDDP-CMIP6** | Clima futuro: 4 modelos, 2 escenarios de emisiones | 1995–2060 |
| **FAO GAEZ v4** | Aptitud del cacao hoy y en 2050 (capa complementaria) | 1981–2010, 2041–2070 |
| **NASA VIIRS** | Verdor (respaldo de MODIS, que se retira) | 2012–2026 |
| **NASA SMAP** | Humedad del suelo casi en tiempo real (monitor de la temporada) | 2015–nov 2026 |

Todo se descarga con scripts propios desde Google Earth Engine para cada área: el país, las
provincias cacaoteras de la costa (Los Ríos, Guayas, Manabí, Esmeraldas, El Oro, Santo Domingo)
y Sucumbíos, y los **125 cantones** de la tabla `areas` de Supabase.

**Corrección del clima.** ERA5 es una simulación y tiene errores: en la costa es demasiado fría y
exagera la lluvia. Se corrige así:
- **Temperatura**: se le suma la diferencia mensual con WorldClim (medido en estaciones).
- **Lluvia**: se ajusta su distribución para que coincida con la de la NASA GPM (*quantile mapping*),
  conservando los extremos de El Niño.

### 2.2 Producción (lo que el modelo aprende a predecir)

| Fuente | Qué es | Años |
|---|---|---|
| **FAOSTAT** producción | Toneladas de cacao producidas en Ecuador | 1961–2025 |
| **FAOSTAT** exportaciones | Toneladas exportadas (grano + pasta + manteca + polvo en equivalente de grano) | 1961–2024 |
| **ESPAC (INEC)** | Producción, hectáreas sembradas y cosechadas por provincia | 2002–2025 |
| FAOSTAT precios | Precio al productor y de exportación | 1961–2024 |

### 2.3 Variables que calcula el modelo (ene–jun, la época lluviosa)

| Variable | Fórmula | Por qué importa |
|---|---|---|
| **Días favorables a la mazorca negra** | días con lluvia ≥ 10 mm, humedad ≥ 90 % y 20–30 °C | Las esporas de *Phytophthora* se dispersan con la lluvia y germinan con humedad alta |
| **Días con el suelo encharcado** | días con humedad del suelo ≥ percentil 90 | Raíces sin oxígeno, más enfermedad |
| **Lluvia total** y **lluvia extrema** | mm; y cuánto supera 2 desviaciones de lo normal | El daño se dispara con la lluvia extrema |
| **Radiación solar** | MJ/m² por día | Más sol, menos humedad sobre la mazorca |
| **Verdor (EVI de MODIS)** | promedio ene–jun | Estado real del cultivo visto desde el espacio |
| Precio del año anterior | precio vs. los 3 años previos | Control: con precio alto se cuida y cosecha más |

La humedad relativa sale de la fórmula de Magnus (FAO-56) con temperatura y punto de rocío.

---

## 3. Cómo funciona el modelo

### 3.1 Qué predice

No predice las toneladas directamente, sino **cuánto se aleja un año de lo normal** en esa zona:

```
anomalía (%) = 100 · (producción del año − tendencia) / tendencia
pérdida (%)  = max(0, −anomalía)
```

La **tendencia** es la producción que tocaría ese año por el crecimiento normal (nuevas
variedades como CCN-51, más hectáreas, mejor manejo). Se calcula con una curva suave (LOWESS)
**sin usar el propio año**, para no hacer trampa.

- **Nacional**: se usa la media de la **producción y las exportaciones** de FAOSTAT. Son dos
  mediciones independientes de la misma cosecha (encuesta y aduanas) y juntas tienen menos error.
- **Provincias**: producción por **hectárea sembrada** (ESPAC). Así cuenta también el área que se
  pierde y ya no se cosecha cuando la enfermedad o el agua arruinan una parcela.

### 3.2 La fórmula

Cada variable se mide como **anomalía de la zona** (`z` = cuántas desviaciones se aleja de su
normal 1991–2020), porque lo que importa es si el año fue más húmedo de lo habitual *para esa zona*.

```
ŷ = b0 − 3,32·z(suelo encharcado) − 2,88·z(días favorables a mazorca negra)
       − 1,16·z(lluvia) − 2,06·[exceso de lluvia sobre 2 desviaciones]
       + 2,73·z(verdor MODIS) + 3,00·z(precio del año anterior)
```

(coeficientes en puntos de % de producción por desviación estándar; regresión **Ridge** con
λ = 31,6 elegido por validación cruzada).

**Por qué este modelo y no uno más complejo**:
- **Signos físicos obligatorios**: más humedad y más lluvia nunca pueden "ayudar" en el modelo,
  porque así funciona la enfermedad. Esto evita que el modelo aprenda casualidades.
- **Con ~200 filas** un modelo complejo (redes neuronales, XGBoost) memoriza en vez de aprender.
  Lo comprobamos: un *gradient boosting* fue peor (0,55) que el Ridge (0,64).
- **Es explicable**: cada predicción se descompone en cuánto aportó cada factor (los
  `top_factors` que ve el usuario).
- **No extrapola**: si el clima es más extremo que cualquier año visto, el modelo no inventa;
  avisa con `extrapolated = true`.

### 3.3 Incertidumbre y probabilidad

- **Rango p10–p90**: el intervalo donde debería caer el resultado 8 de cada 10 veces. Se calcula con
  los errores reales del modelo en años que no vio. Cubre el 80 % nacional y el 76 % en provincias.
- **Probabilidad de año malo** (`prob_loss_gt20`): probabilidad de perder más del 20 %. Sale del
  mismo modelo y su distribución de errores.

### 3.4 Prueba con datos falsos (antes de usar los reales)

Antes de entrenar con datos reales generamos **datos sintéticos con una respuesta conocida**.
El modelo recuperó la verdad con correlación > 0,9 y, cuando el clima **no** afectaba nada,
no inventó señal (correlación ≈ 0). Eso prueba que el método no tiene fugas de información.

---

## 4. Qué tan bueno es

### 4.1 Cómo se valida: *leave-one-year-out*

Para cada uno de los 65 años: se **borra ese año** (del entrenamiento, de la tendencia y de la
normal climática), se entrena con los demás y se predice el año borrado. Así se simula predecir
una temporada que el modelo nunca vio. Se repitió dejando fuera **bloques de 3 años** para
descartar que dependa de años vecinos, y un auditor independiente (subagente) revisó que no
hubiera fugas de información.

### 4.2 Resultados

**Serie nacional (65 años)**

| Método | Error medio | RMSE | Correlación | R² fuera de muestra |
|---|---|---|---|---|
| Decir siempre "año normal" | 12,6 | 18,1 | — | 0,00 |
| Niño sí/no según el índice ONI | 12,6 | 17,9 | 0,22 | 0,02 |
| Regla "si llueve más del doble, pérdida grande" | 11,3 | 15,2 | 0,54 | 0,30 |
| Gradient boosting cuantílico | 11,0 | 15,2 | 0,55 | 0,30 |
| **Modelo final (Ridge con signos)** | **10,0** | **13,9** | **0,64** | **0,41** |

- **Correlación 0,64**: cuando el modelo dice "año malo", en general lo fue.
- **R² 0,41**: el clima explica cerca del **41 %** de cómo varía la cosecha de un año a otro. El
  resto lo explican cosas que el clima no ve (crisis económicas, manejo, errores de las estadísticas).
- **Detecta el 80 % de los años con pérdida grande** (> 20 %) sin falsas alarmas.

**Provincias (137 años-provincia, 2002–2025)**: correlación **0,32**, R² 0,10. Es una señal más
débil porque la encuesta ESPAC tiene mucho error de muestreo (±15–31 %), pero es **real**.

**¿Es casualidad?** Se repitió todo 200 veces **revolviendo el clima entre años** al azar. Con el
clima revuelto el modelo nunca logró lo que logra con el clima real:
**p = 0,005** nacional y **p = 0,01** provincias (lo normal en ciencia es exigir p < 0,05).

**Probabilidad de año malo**: AUC **0,87**. Entre un año malo y uno bueno elegidos al azar, el
modelo le da más riesgo al malo 87 de cada 100 veces. Sin haberlos visto, a **1983 le dio 97 %**
y a **1998 87 %** de probabilidad de pérdida grave (la frecuencia histórica es 6 %).

### 4.3 Los Niños de la historia (predicción sin haber visto cada año)

| Año | Real | Predicho | Rango p10–p90 |
|---|---|---|---|
| **1983** (Niño costero extremo) | −50 % | **−54 %** | −74 a −34 % |
| 1987 | −28 % | −12 % | −32 a +9 % |
| 1992 | −11 % | −20 % | −37 a −2 % |
| **1998** (Niño costero extremo) | −64 % | **−36 %** | −54 a −15 % |
| 2016 (Niño fuerte, sin lluvia extrema en la costa) | −6 % | −2 % | −22 a +19 % |
| 2023–2024 (Niño fuerte, sin lluvia extrema) | −5 / −7 % | −2 / +8 % | — |

---

## 5. Qué responde: escenarios de hoy

Pérdida esperada de producción por escenario (media de los años de cada tipo):

| Área | Año normal | Niño (ONI) | Niña | **Niño extremo** (1983/1998) | **Temporada 2027** |
|---|---|---|---|---|---|
| **Ecuador** | 3,2 % | 1,5 % | 3,0 % | **52,9 %** | **20,5 %** |
| El Oro | 3,0 % | 2,0 % | 2,4 % | 57,4 % | 21,3 % |
| Guayas | 3,8 % | 1,3 % | 3,4 % | 56,3 % | 20,0 % |
| Manabí | 3,6 % | 1,4 % | 4,5 % | 53,3 % | 17,2 % |
| Santo Domingo | 1,9 % | 2,0 % | 3,6 % | 47,2 % | 18,6 % |
| Los Ríos | 3,4 % | 1,8 % | 3,4 % | 44,2 % | 19,6 % |
| Esmeraldas | 5,8 % | 3,4 % | 3,0 % | 30,4 % | 12,2 % |

- **Niño extremo**: con la probabilidad de año malo del **98 %** a nivel nacional.
- **Temporada 2027 (`actual`)**: hoy (octubre de 2026) el mar frente a Ecuador (Niño 1+2) está en
  **+5,3 °C**, más caliente que en 1997 antes del Niño de 1998. El modelo usa los años con un mar
  igual de caliente en ago–oct (1998, 2016, 2024): uno fue un desastre y dos no. Por eso da
  **~21 %** con un rango amplio. Se actualiza solo al correr de nuevo con los datos de NOAA.
- **Por cantón** (125): en un Niño extremo los de la costa pierden 40–57 % (Machala, Manta, Pasaje,
  Santa Rosa, Guayaquil ~57 %). En la Amazonía, 3–5 %.
- Cada resultado trae **toneladas y dólares** perdidos (hectáreas ESPAC × rendimiento de
  tendencia × precio), el rango p10–p90, la probabilidad de año malo y los factores que más pesan.

---

## 6. 2026–2050: el clima futuro

### 6.1 Cómo se calcula

1. Se bajan las proyecciones **NASA NEX-GDDP-CMIP6** de 4 modelos climáticos (ACCESS-CM2,
   EC-Earth3, GFDL-ESM4, MRI-ESM2-0) para dos escenarios: **emisiones moderadas (SSP2-4.5)** y
   **emisiones altas (SSP5-8.5)**.
2. Para cada año futuro se calcula **cuánto cambia** la temperatura, la humedad y la lluvia de cada
   mes (promedio de los 21 años alrededor de ese año, frente a 1995–2014 del mismo modelo, para
   cancelar sus sesgos).
3. Ese cambio se aplica al clima diario observado y se pasa por el mismo modelo, para un **año
   típico** y para un **Niño extremo** como 1998.
4. Se calcula para **todos los años de 2026 a 2050**, para el país, las provincias y los 125 cantones.

**Cambio en la costa en 2050 (ene–jun)**: **+1,2 °C y +4 % de lluvia** (emisiones moderadas);
**+1,6 °C y +9 % de lluvia** (emisiones altas).

### 6.2 Resultados nacionales

| | Hoy | 2030 | 2040 | **2050** |
|---|---|---|---|---|
| Año típico, emisiones moderadas | ~4,8 % | 4,7 % | 5,0 % | **5,1 %** [4,1–7,4] |
| Año típico, emisiones altas | ~4,8 % | 5,0 % | 5,0 % | **5,3 %** [3,8–7,5] |
| Niño extremo, emisiones altas | ~53 % | 52 % | 52 % | **53 %** [46–58] |
| **Pérdida anual esperada**, misma frecuencia de Niños | 6,4 % | 6,5 % | 6,5 % | **6,8 %** |
| **Pérdida anual esperada**, Niños extremos ×2 | 6,4 % | 6,8 % | 7,3 % | **8,2 %** |

(Entre corchetes: rango entre los 4 modelos climáticos.)

La **pérdida anual esperada** combina años típicos y Niños extremos según cada cuánto ocurren:
`(1 − p)·pérdida_típica + p·pérdida_Niño_extremo`, con p = 2/65 hoy (1983 y 1998). El escenario
"×2" usa la proyección de **Cai et al. (2014, *Nature Climate Change* 4:111–116)**: con el
calentamiento, los Niños extremos pasan de ~1 cada 20 años a ~1 cada 10.

### 6.3 Qué significa

- **El calentamiento solo cambia poco un año normal** (+0,5 puntos): la costa ya es cálida y
  húmeda, y los hongos siguen igual de cómodos con 1–2 °C más.
- **El riesgo real es la frecuencia de los Niños extremos**: si se duplican, la pérdida anual
  esperada sube **un 28 %** (de 6,4 % a 8,2 % de la cosecha).

---

### 6.4 ¿Seguirá siendo buena la zona para el cacao? (FAO GAEZ v4)

Con los mapas oficiales de aptitud de la FAO (GAEZ v4, recurso del reto) la **aptitud del cacao mejora
hacia 2050 en la costa** (nacional +15 %; Los Ríos +19 %, Manabí +22 %, Santo Domingo +17 %) por más
lluvia y calor. Cruzando aptitud y riesgo por El Niño sale una **matriz de decisión por cantón**:

| | Pérdida baja en Niño extremo | Pérdida alta en Niño extremo |
|---|---|---|
| **Apta en 2050** | **segura** (27 cantones): seguir con cacao | **manejo** (29): invertir en drenaje, cosecha sanitaria, poda y seguro |
| **Poco apta en 2050** | **transición** (18): diversificar de a poco | **crítica** (51): otro cultivo o sistema mixto |

Los Ríos, Manabí, Esmeraldas y Santo Domingo quedan en **manejo**: seguirán siendo cacaoteras, pero muy
expuestas a los Niños extremos. Cantones prioritarios: Jama, Baba, Muisne, Pedernales, Santo Domingo,
Chone, La Concordia, Vinces. (Guayas y El Oro salen "críticas" porque GAEZ evalúa cacao de secano y allí
se riega mucho: su aptitud real es mayor.) Archivo: [`artifacts/zones_v1.csv`](artifacts/zones_v1.csv).

### 6.5 La temporada en curso, vista desde el espacio (NASA SMAP) y el respaldo de MODIS (NASA VIIRS)

- **Monitor de humedad del suelo (SMAP, ~3 días de retraso)**: en noviembre de 2026 el suelo de la costa
  está **tan húmedo como en marzo** (pico de la época de lluvias) en plena época seca: **+59 %** sobre lo
  normal a nivel nacional, Guayas +131 %, El Oro +120 %, Los Ríos +101 %, Manabí +89 %; **85 de 125
  cantones encharcados**. Es la señal del Niño costero de 2026 trayendo lluvia fuera de temporada, como
  a fines de 1997. Archivo: [`artifacts/monitor_soil_v1.csv`](artifacts/monitor_soil_v1.csv) (se actualiza cada mes).
- **VIIRS como respaldo de MODIS**: MODIS va en Terra, que la NASA está retirando. El modelo ya sabe usar
  VIIRS calibrado si falta MODIS; probado: el resultado nacional no cambia y el provincial conserva la
  mayor parte de la ganancia del verdor (0,28 frente a 0,325).

## 7. Hallazgos principales

1. **Lo que destruye el cacao no es "El Niño" en general, sino el Niño costero con lluvia
   extrema.** Muchos años marcados como Niño por el índice oficial (ONI) casi no causaron pérdidas
   (2016, 2023, 2024). Lo que separa un desastre de un año normal es la **lluvia extrema en la costa**
   y el **suelo encharcado** durante enero–junio.
2. **El daño es propio de la costa ecuatoriana.** Entrenando con Colombia y Perú, el modelo empeora:
   allí la lluvia casi no daña al cacao (en la Amazonía peruana incluso ayuda). En la Amazonía
   ecuatoriana el modelo también da pérdidas bajas.
3. **El efecto del clima es real y no es un disfraz del precio.** Al controlar por el precio del
   cacao, los coeficientes del clima casi no cambian.
4. **Hay tres fuentes independientes que confirman 1998**: la producción cayó −59 %, las
   exportaciones se desplomaron y **las compras de la Unión Europea a Ecuador cayeron 41 %**.
5. **Ya hay señal de la temporada 2027**: el mar frente a Ecuador está más caliente que en 1997 y el
   satélite SMAP muestra el suelo de la costa encharcado en plena época seca (+59 % sobre lo normal).
6. **Hacia 2050 el peligro es que los Niños extremos sean más frecuentes**, no el calentamiento
   promedio. Prepararse para ellos (drenaje, cosecha sanitaria, poda) es la adaptación que más vale.
7. **La costa seguirá siendo apta para el cacao en 2050** (FAO GAEZ: la aptitud incluso mejora), pero más
   expuesta: por eso la mayoría de los cantones cacaoteros quedan en la zona de **manejo** (adaptarse,
   no abandonar el cultivo).

---

## 8. Cómo llegamos aquí: lo que mejoró y lo que no

Todo se evaluó con la misma validación estricta. Solo se adoptó lo que mejoró de forma clara.

### Adoptado (mejoró)

| Mejora | Efecto |
|---|---|
| Medir la cosecha nacional con **producción + exportaciones** | Nacional 0,54 → 0,64 |
| **Verdor del cultivo desde el satélite** (MODIS, recurso del reto) | Provincias 0,10 → 0,20 |
| Producción provincial por hectárea **sembrada** | Provincias 0,20 → 0,28 (p = 0,01) |
| **Precio** del año anterior como control | Provincias 0,28 → 0,32 |

### Probado y descartado (18 ideas)

| Idea | Por qué no |
|---|---|
| Modelos más complejos (gradient boosting, ensamble) | Peores con ~200 filas |
| Daño de los años posteriores al Niño | Las caídas de 2000–2002 fueron por la crisis de la dolarización |
| Lluvia CHIRPS, GPM observado, suelo de GLDAS | Iguales o peores; CHIRPS suaviza los extremos |
| Otros meses (ene–abr, feb–may…), lluvia de oct–dic previa | Ninguno supera a ene–jun |
| Horas de hoja mojada (ERA5 horario) | Mismo contenido que los días favorables |
| Verdor solo en píxeles de cultivo, NDVI, otros meses (26 variantes) | Sin mejora clara |
| 4 provincias andinas más (+96 filas) | Su estadística tiene aún más ruido |
| Ancho de la tendencia, sensibilidad propia por provincia | Mismo resultado o riesgo de fallar en Niños extremos |
| Clima provincial promediado desde los cantones | Sin mejora |
| Target provincial "limpiado", regresión robusta (Huber), recorte | ±0,01 (ruido); recortar empeora |
| Importaciones de la UE (Eurostat 1988–2025), exportaciones mensuales (Comtrade 2010–2025) | Más ruido que señal |
| Aprender también de Colombia y Perú | Diluye el daño propio de la costa ecuatoriana |
| Alerta temprana en octubre/enero solo con El Niño | Falsas alarmas (2016, 2024): haría falta un pronóstico de lluvia |

**Conclusión**: el límite lo ponen los datos de producción (solo dos Niños extremos en 65 años y
estadísticas provinciales con mucho ruido), no el algoritmo. Para ir más allá haría falta otra
fuente de producción real: exportaciones mensuales del Banco Central, reportes de ANECACAO o
rendimientos de ensayos del INIAP.

---

## 9. Límites (lo que hay que decir con honestidad)

- **Lo validado es lo nacional.** Por provincia la señal es real pero pequeña (explica ~10 % de la
  variación). Por **cantón** es un **índice de riesgo**: no existen datos de producción por cantón
  para comprobarlo (`evidence = indice_subnacional_no_validado`).
- **La señal fuerte viene de pocos eventos.** Solo hubo dos Niños costeros extremos (1983 y 1998);
  por eso los rangos de incertidumbre son anchos.
- **En años normales el clima explica poco**: allí pesan el precio, el manejo y otras plagas.
- **Las hectáreas por cantón son aproximadas**: el total de cada provincia es real (ESPAC 2025);
  el reparto entre cantones usa la superficie de cultivo y árboles de ESA WorldCover.
- **2050 es una proyección**: el modelo no extrapola más allá del clima que vio, así que la pérdida
  futura puede estar subestimada; la duplicación de Niños extremos es un supuesto de la literatura,
  no una salida del modelo (`evidence = proyeccion_cmip6_no_validada`).
- **Los umbrales de enfermedad** (humedad, temperatura, lluvia) son de la literatura y deben
  validarse con el INIAP.
- La Amazonía tiene otro régimen de lluvia; sus resultados son orientativos.

---

## 10. Qué se entrega al equipo y cómo se usa

| Archivo | Qué es | Para quién |
|---|---|---|
| [`artifacts/loss_predictions_areas_v1.csv`](artifacts/loss_predictions_areas_v1.csv) | **132 áreas** (país, provincias, 125 cantones) × **7 escenarios** (`normal`, `nino`, `nina`, `nino_extremo`, `actual`, `ssp245_2050`, `ssp585_2050`), con `area_id` = uuid de Supabase | Backend / Supabase (`loss_predictions`) y front (mapa) |
| [`artifacts/projections_v1.csv`](artifacts/projections_v1.csv) | Trayectoria **año por año 2026–2050** por área y escenario de emisiones | Front (gráfico de evolución) |
| [`artifacts/cacao_loss_v1.joblib`](artifacts/cacao_loss_v1.joblib) | El modelo para el backend (en memoria) | Backend (`MODEL_PATH`) |
| [`inference.py`](inference.py) | `predict()` y `adjust_features()` (sliders de lluvia, temperatura y El Niño) | Backend (`ML_INFERENCE_MODULE=ml.inference`) |
| [`artifacts/monitor_soil_v1.csv`](artifacts/monitor_soil_v1.csv) | Humedad del suelo por área y mes (SMAP): estado, % sobre lo normal | Front (banner de la temporada) |
| [`artifacts/zones_v1.csv`](artifacts/zones_v1.csv) | Matriz de decisión por área: zona (segura/manejo/transición/crítica), recomendación, aptitud GAEZ hoy y 2050 | Front (ZoneMatrix) y Supabase (`zone_classification`) |
| [`artifacts/model_card_v1.json`](artifacts/model_card_v1.json) | Ficha: fórmula con todos sus números, métricas y límites | Página de metodología |
| [`artifacts/model_version_v1.json`](artifacts/model_version_v1.json) | Fila para la tabla `model_versions` | Supabase |

**Campos principales de cada predicción**

| Campo | Significado |
|---|---|
| `loss_pct` | Pérdida esperada de producción (%) |
| `loss_pct_low` / `loss_pct_high` | Rango p10–p90 (mostrarlo siempre) |
| `prob_loss_gt20` | Probabilidad de perder más del 20 % (semáforo) |
| `loss_t`, `loss_usd` | Toneladas y dólares perdidos |
| `risk_class` | bajo / medio / alto / muy_alto |
| `top_factors` | Factores que más suman a la pérdida (`contribution_pct > 0` = suma) |
| `evidence` | `validado_nacional` · `indice_subnacional_no_validado` · `proyeccion_cmip6_no_validada` |
| `extrapolated` | El clima es más extremo que cualquier año de entrenamiento |
| `annual_loss_pct_*` (2050) | Pérdida anual esperada hoy y en 2050 (frecuencia de Niños actual y ×2) |

**Cómo regenerar todo**

```bash
ml/.venv/bin/python -m ml.dataset          # panel de entrenamiento
ml/.venv/bin/python -m ml.train --perm 200 # entrena, valida y guarda el modelo (~10 min)
ml/.venv/bin/python -m ml.predict          # país y provincias
ml/.venv/bin/python -m ml.cantons_predict  # cantones (necesita ml.etl.cantons una vez)
ml/.venv/bin/python -m ml.projections      # 2026–2050 (necesita ml.etl.cmip6 una vez)
ml/.venv/bin/python -m pytest ml/tests     # 59 tests
```

---

## 11. Glosario

| Término | Qué quiere decir |
|---|---|
| **Anomalía** | Cuánto se aleja un año de lo normal para esa zona |
| **Tendencia** | Producción esperada por el crecimiento normal del sector, sin el clima |
| **Correlación** | De 0 a 1: qué tan bien el modelo acierta la dirección (año bueno o malo) |
| **R² fuera de muestra** | Qué parte de la variación entre años explica el modelo en años que no vio |
| **RMSE** | Error típico de la predicción, en puntos de % |
| **AUC** | Probabilidad de que el modelo le dé más riesgo a un año malo que a uno bueno |
| **p (permutación)** | Probabilidad de obtener el resultado por casualidad (menor a 0,05 = señal real) |
| **p10–p90** | Rango donde debería caer el resultado 8 de cada 10 veces |
| **Leave-one-year-out** | Validar prediciendo cada año sin haberlo visto en el entrenamiento |
| **Niño costero** | Calentamiento del mar frente a Ecuador y Perú (índice Niño 1+2), el que trae lluvia extrema a la costa |
| **ONI** | Índice oficial de El Niño en el Pacífico central; no siempre trae lluvia a la costa |
| **SSP2-4.5 / SSP5-8.5** | Escenarios de emisiones moderadas / altas del IPCC |
| **Método delta** | Sumar al clima observado el *cambio* que proyecta el modelo climático |
