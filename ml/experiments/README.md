# Experimentos (no cambian el modelo)

Cada experimento usa la misma validación que el modelo (leave-one-year-out sin fuga, y bloques de
3 años) y escribe sus resultados en `results/`. El modelo de `ml/model.py` y sus artefactos no se
tocan: algo se adopta solo si mejora de forma clara.

```bash
ml/.venv/bin/python -m ml.experiments.hourly_wetness   # descarga ERA5-Land horario (GEE, ~45 min)
ml/.venv/bin/python -m ml.experiments.wetness_model    # Exp. 1
ml/.venv/bin/python -m ml.experiments.probability      # Exp. 3
ml/.venv/bin/python -m ml.experiments.early_warning    # Exp. 4
```

Referencia, modelo actual: nacional corr 0,64 (R² 0,41) · provincias corr 0,32 (R² 0,10).

## Exp. 1 — Horas de hoja mojada (ERA5-Land horario) · NO mejora

Horas con HR ≥ 90 % (y 20–28 °C, y de noche) por píxel y hora, ene–jun 1961–2025.

| Variante | Nacional corr / R² | Provincias corr / R² |
|---|---|---|
| Modelo actual (días favorables, diario) | 0,643 / 0,408 | 0,325 / 0,103 |
| + horas de infección | 0,643 / 0,409 | 0,316 / 0,097 |
| Horas de infección en vez de días favorables | 0,637 / 0,401 | 0,308 / 0,093 |
| + horas mojadas de noche | 0,644 / 0,409 | 0,319 / 0,100 |
| + horas mojadas | 0,646 / 0,412 | 0,319 / 0,099 |

Las horas mojadas coinciden en un 77 % con los días favorables diarios, y el indicador diario se
relaciona mejor con la pérdida (−0,36 vs −0,26/−0,30). A escala de provincia y año el detalle
horario no aporta: la información ya está en el indicador diario.

## Exp. 3 — Probabilidad de año malo, P(pérdida > 20 %) · ÚTIL como salida extra

| Nacional (5 años malos de 65) | Brier skill | AUC |
|---|---|---|
| Frecuencia histórica | 0 | — |
| Regresión logística (mismas variables) | 0,26 | 0,88 |
| **Probabilidad del modelo actual** (predicción + errores fuera de muestra) | **0,29** | **0,87** |
| Provincias (23 de 137), modelo actual | 0,05 | 0,66 |

- Sin haber visto el año: 1983 → **97 %**, 1998 → **87 %** de probabilidad de año malo (frecuencia
  histórica 6 %); 2016 → 14 %, 2024 → 4 % (no fueron malos).
- AUC 0,87: entre un año malo y uno bueno al azar, el modelo da más riesgo al malo 87 de cada 100 veces.
- No hace falta otro modelo: la probabilidad sale del actual. Se puede añadir a la salida de la API
  como `prob_loss_gt20`.

## Exp. 4 — Alerta temprana (antes de la temporada) · NO sirve con solo ENSO

| Momento del aviso | Nacional corr / R² | AUC año malo | Provincias corr |
|---|---|---|---|
| Octubre del año anterior (Niño 1+2 y ONI ago–oct) | 0,30 / 0,09 | 0,66 | 0,04 |
| Enero (+ Niño oct–dic y lluvia/suelo oct–dic) | 0,42 / 0,15 | 0,58 | 0,07 |
| Julio (modelo actual, clima ene–jun) | 0,64 / 0,41 | 0,87 | 0,32 |

| Nacional: pérdida / prob. año malo | 1983 | 1987 | 1998 | 2016 | 2024 |
|---|---|---|---|---|---|
| Octubre | −4 % / 17 % | −1 % / 11 % | −8 % / 23 % | −8 % / 26 % | −33 % / 76 % |
| Enero | −23 % / 60 % | 1 % / 10 % | −11 % / 30 % | −18 % / 47 % | −15 % / 42 % |
| Julio | −54 % / 97 % | −12 % / 30 % | −36 % / 87 % | −2 % / 14 % | 8 % / 4 % |
| **Real** | −50 % | −28 % | −64 % | −6 % | −7 % |

El mar caliente en oct–dic no garantiza lluvia extrema en la costa en ene–jun (2016, 2024: falsas
alarmas). Para avisar antes de la temporada haría falta un **pronóstico estacional de lluvia**
(p. ej. Copernicus C3S o NMME), no solo el índice de El Niño. Por eso el escenario `actual` usa
años análogos con un rango amplio.

## Exp. 5 — Clima provincial = promedio de sus cantones ponderado por cultivo · NO mejora

`ml.experiments.canton_weighted`. Features calculadas en cada cantón (con su corrección de sesgo) y
promediadas por provincia con peso = superficie de cultivo + árboles < 900 m (o pesos iguales).

| Clima provincial | Nacional corr / R² | Provincias corr / R² |
|---|---|---|
| Provincia entera < 900 m (actual) | 0,643 / 0,408 | **0,325 / 0,103** |
| Cantones ponderados por cultivo | 0,647 / 0,411 | 0,317 / 0,098 |
| Cantones, pesos iguales | 0,648 / 0,411 | 0,310 / 0,094 |

El promedio provincial ya captura la señal climática; lo que limita en provincias es el ruido del
target (encuesta ESPAC), no la medición del clima.

## Exp. 6 — Entrenar con el target provincial "limpiado" hacia el nacional · NO mejora

`ml.experiments.shrink_target`. y' = λ·y_provincia + (1−λ)·y_nacional del mismo año, solo al entrenar;
se evalúa contra el dato provincial crudo.

| λ | Nacional corr | Provincias corr / R² | Provincias, bloques de 3 años |
|---|---|---|---|
| 1 (actual) | 0,643 | 0,325 / 0,103 | 0,284 |
| 0,75 | 0,646 | 0,327 / 0,105 | 0,289 |
| 0,50 | 0,647 | 0,322 / 0,101 | 0,290 |
| 0,25 | 0,643 | 0,313 / 0,094 | 0,298 |

Diferencias de ±0,01: ruido. El modelo está en el techo que permiten estos datos de producción.

## Exp. 7 — Más fuentes de producción (comercio exterior) · NO mejoran

Se buscaron y descargaron todas las series de comercio que se pueden bajar automáticamente:

| Fuente | Qué se consiguió | Resultado |
|---|---|---|
| Banco Central del Ecuador (Información Estadística Mensual, tabla 3.1.2) | Solo totales anuales en USD 2020–2025 | La serie mensual larga está en un visualizador interactivo sin descarga automática |
| ANECACAO InfoCacao | — | Requiere usuario y contraseña |
| **Eurostat Comext**: importaciones de la UE desde Ecuador (grano, pasta, manteca, polvo) | **Mensual 1988–2025** (`ml/data/raw/eurostat/`) | Como 3.ª medida de la cosecha: corr nacional 0,64 → 0,57 (año) / 0,51 (abr–sep); contra la producción sola 0,578 → 0,575. La cuota de Europa en las compras cambió mucho (Asia), mete ruido |
| **UN Comtrade**: exportaciones de Ecuador, HS 1801 | Mensual 2010–2025, con huecos (2022–2023, límite de la API gratuita) (`ml/data/raw/comtrade/`) | Cosecha principal (abr–sep) vs año completo: la predicción del modelo se relaciona más con el año completo (0,67) que con abr–sep (0,51). Sin Niños extremos en 2010–2025 |

`ml.experiments.eu_imports` reproduce la prueba de Eurostat (`results/exp7_eu_imports.json`).
Dato llamativo: en 1998 las importaciones de la UE desde Ecuador cayeron un 41 % (15 936 → 9 396 t),
coherente con la pérdida que estima el modelo.
