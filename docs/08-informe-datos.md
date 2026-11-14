# 8. Informe de datos — qué hay cargado, de dónde sale y qué falta

Actualizado: 2026-11-14 (segunda carga). Archivos: [`supabase/seed/`](../supabase/seed/README.md). Cómo conseguir lo que falta: [09](09-como-conseguir-los-datos-que-faltan.md).
**Real** = descargado de la fuente oficial. **Sintético** = inventado para probar el sistema.

## 1. Resumen de lo cargado en Supabase

| Bloque | Estado | Filas |
|--------|--------|------:|
| Catálogos (fuentes, variables, cacao, requisitos, enfermedades, umbrales, fenología, escenarios, estrategias) | **Real / referencial** (migraciones 0001–0008) | ~90 |
| Territorio: Ecuador, **12 provincias** (6 Costa + 6 Amazonía), **126 cantones** | **Real** (geoBoundaries / INEC) | 139 |
| **Códigos DPA** del INEC: 12/12 provincias, 124/126 cantones | **Real** (HDX COD-AB) | — |
| El Niño (ONI y regiones Niño 1+2, 3, 3.4, 4, 1990–oct 2026) + 24 eventos | **Real** (NOAA CPC) | 2 209 + 24 |
| Clima mensual (11 variables: temperatura media/máx/mín, humedad, lluvia, suelo, días de lluvia/aguacero/calor/helada/saturados) y conteos de peligro | **Real** (ERA5 vía Open-Meteo) | 84 546 + 7 686 |
| Altitud y pendiente (SRTM 30 m) y suelo (SoilGrids) por área | **Real** | 138 |
| Riesgo de enfermedad por mes / por escenario | **Calculado** con umbrales por validar | 23 058 + 5 832 |
| Aptitud ECOCROP (provincias) | **Calculada** (ver aviso de lluvia) | 12 |
| Producción nacional de cacao 2001–2024 | **Real** (FAOSTAT) | 24 |
| **Producción por provincia 2023, 2024 y 2025** | **Real** (ESPAC, INEC) | 36 + 3 nacionales |
| Producción por provincia 2001–2022 | **SINTÉTICA** (proporciones ancladas en ESPAC) | 264 |
| Hectáreas por provincia (2025) | **Real** (ESPAC) | 12 |
| Hectáreas por cantón | **SINTÉTICAS** (provincia repartida por superficie) | 126 |
| Precio internacional del cacao, mensual 2001–2026 | **Real** (FMI vía FRED) | 309 |
| Observaciones de moniliasis / escoba de bruja | **Real** (GBIF) | 12 |
| Modelo y predicciones de pérdida | **DEMO** (fórmula fija, no entrenado) | 1 + 276 |

## 2. Fuentes

| Dato | Fuente | Licencia / cita | Cobertura cargada |
|------|--------|-----------------|-------------------|
| Límites | geoBoundaries gbOpen ECU ADM1/ADM2 (INEC, OCHA ROLAC), v2019, simplificados | CC BY 3.0 IGO | 12 provincias y 126 cantones de Costa y Amazonía |
| Códigos DPA | HDX COD-AB Ecuador (`ecu_admgz.xlsx`, INEC/OCHA) | CC BY-IGO | 24 provincias, 224 cantones (5 cantones con nombre abreviado en geoBoundaries se asignaron a mano) |
| El Niño | NOAA CPC `oni.ascii.txt`, `sstoi.indices` | Dominio público | 1990–oct 2026 |
| Clima | Open-Meteo Historical API, `era5_seamless` (ERA5 + ERA5-Land) | CC BY 4.0 + Copernicus | Provincias: diario 2001–2025. Cantones: ene–jun de 2018, 2020, 2023, 2024, 2025 y 2016 (51 de 126) |
| Altitud y pendiente | SRTM 30 m vía OpenTopoData | NASA SRTM | 16 puntos por polígono; pendiente con vecinos a ~100 m |
| Suelo | SoilGrids v2 (ISRIC), 0–30 cm ponderado | CC BY 4.0 | 133 de 138 áreas (5 sin dato: píxeles urbanos o con agua) |
| Producción provincial | **ESPAC (INEC)**, tabulado T14 "cacao (almendra seca)" 2023, 2024, 2025 (solo + asociado) | INEC | 12 provincias; suman exactamente el total nacional |
| Producción nacional | FAOSTAT `QCL` *Cocoa beans* | CC BY 4.0 | 2001–2024 (coincide con ESPAC en 2023–2024) |
| Precio | FRED `PCOCOUSDM` | FMI | 2001–sep 2026 |
| Observaciones | GBIF, *M. roreri* y *M. perniciosa* | CC BY / CC0 | 12 de 42 (los demás no traen fecha) |

## 3. Datos sintéticos — cómo se generaron

| Dato | Método |
|------|--------|
| Producción provincial 2001–2022 | Rendimiento = tendencia lineal nacional (FAOSTAT) × **proporción real de la provincia** (rendimiento ESPAC de la provincia ÷ nacional, 2023–25) × ruido × (1 − pérdida sembrada), donde la pérdida sembrada crece con el riesgo de enfermedad del año (hasta 40 %). Área cosechada = área nacional × **proporción real de superficie** (ESPAC) |
| Hectáreas por cantón | Hectáreas reales de la provincia (ESPAC 2025) repartidas por superficie del cantón |
| Modelo demo | `loss = clip(10 + 150 × (riesgo ene–jun − riesgo medio del área), 0, 60)` |

Marcados con `source_id = 'seed_sintetico'`, "SINTÉTICO" en `notes` y el modelo `cacao_loss_demo_sintetico`.
**La señal clima → pérdida está plantada**: un modelo entrenado con ellos la "encontrará" por construcción.

## 4. Hallazgos de calidad

1. **El riesgo de moniliasis casi no discrimina.** Con *HR media diaria ≥ 80 % y 20–28 °C*, el
   58 % de los meses por área sale ≥ 0,95. La mazorca negra sí varía. Acción: subir el umbral de HR,
   usar horas de humedad o rachas de días; validar con el INIAP.
2. **ERA5 sobreestima la lluvia en la Costa y la Amazonía** (Los Ríos ≈ 5 400 mm/año contra un óptimo
   de 1 200–3 000). La aptitud sale "marginal/no apta" en zonas que sí producen. Calibrar con GPM IMERG
   (NASA) o con el INAMHI.
3. **Años Niño 2001–2025** (ONI ≥ 0,5 o Niño 1+2 ≥ 0,4, promedio ene–jun): 2010, 2015, 2016, 2017
   (costero), 2019, 2023, 2024, 2025. Niña: 2008, 2011, 2021, 2022. **1997–98 no entra.**
4. **Cantones con pocos años:** escenario *normal* = 2018 y 2020; *Niño* = 2023, 2024, 2025 (+2016 en
   51 cantones). **No hay escenario Niña en cantones** (faltan 2022 y 2021). El límite diario de
   Open-Meteo frenó la descarga; faltan 2016 (75 cantones), 2015, 2022 y 2014.
5. **Datos reales de producción provincial solo de 3 años** (2023–2025): el modelo real aún no puede
   entrenarse con datos reales. Los años anteriores a 2023 del ESPAC existen, pero el INEC no los
   publica en una dirección predecible: hay que bajarlos de su página.
6. **Altitud:** hay cantones de la Amazonía y de Santo Domingo por encima de 900 m (óptimo máximo del
   cacao en ECOCROP); la aptitud de cantones no se calculó (solo hay ene–jun).
7. **Sierra fuera de alcance:** Bolívar, Cañar, Pichincha y Cotopaxi tienen cacao (5 000–11 000 ha)
   pero no se cargaron; `crop_phenology` solo define Costa y Amazonía.
8. **Elevación de cantones** = promedio de 16 puntos dentro del polígono (no un modelo digital completo).
9. **GBIF:** solo 12 observaciones con fecha: sirven para validar, no para entrenar.

## 5. Lo que todavía falta

| Pendiente | Cómo | Quién |
|-----------|------|-------|
| ESPAC 2014–2022 por provincia | Descargar los tabulados anuales (T14 cacao) desde la página de ESPAC del INEC y cargarlos como `source_id = 'espac'` | Datos |
| Clima de cantones restante (2016, 2015, 2022, 2014) | Relanzar `fetch_weather.py` al día siguiente (retoma sin repetir) | Datos |
| Precio **Ecuador** (grano seco) | SIPA / MAG (sin descarga automática) | Datos |
| Clima NASA (GPM, SMAP, MODIS) y cobertura (WorldCover) | ETL con Earth Engine (hoy: ERA5) | Backend |
| Proyecciones 2050 | NEX-GDDP-CMIP6 → `area_scenario_climate` (`ssp245_2050`, `ssp585_2050`) | Fase 2 |
| Reducciones de las estrategias y costos | Literatura / INIAP → `strategy_effects`, `adaptation_strategies.cost_usd_ha_year` | Agrónomo |
| Validar umbrales de enfermedad, ventana de riesgo y umbral de Niño costero | INIAP / fitopatólogo / INAMHI → `validated = true` | Agrónomo |
| Entrenar el modelo real | `ml/train.py` sobre `v_training_area_year` | ML |

## 6. Cómo se verificó

- **Prueba completa con rollback** (volumen real: ~7 MB de SQL) antes de cargar: las 6 partes entraron,
  139 polígonos válidos, `v_loss_map` 276 filas, `v_training_area_year` 300 filas completas
  (12 provincias × 25 años).
- **Control de ESPAC:** la suma de las provincias coincide con el total nacional en 2023, 2024 y 2025
  (375 719, 403 699 y 501 244 t). Esa comprobación detectó un error de lectura (filas "Asociado" omitidas)
  que se corrigió.
- **Cobertura:** 11 de 24 variables del catálogo tienen datos; las 13 pendientes dependen de datos NASA (ver `v_variable_coverage`).
- **Auditoría de consistencia** (17 comprobaciones en SQL): sin huérfanos ni duplicados; las hectáreas de los cantones suman la de su provincia; las 12 provincias tienen riesgo 2001–2025; 2 observaciones de GBIF caen fuera de los cantones cargados (área nula).
- **Carga real** con `inject.py --reset --yes`: 6 partes en ~11 s; revisor de seguridad de Supabase: 0 alertas.
- Hallazgos de la primera carga ya corregidos: 3 polígonos inválidos (`st_makevalid`), formato del JSON
  de `top_factors` y fórmula demo.
