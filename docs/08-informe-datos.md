# 8. Informe de datos — qué hay cargado, de dónde sale y qué falta

Fecha de generación: 2026-11-14. Archivos: [`supabase/seed/`](../supabase/seed/README.md).
**Real** = descargado de la fuente oficial. **Sintético** = inventado para probar el sistema.

## 1. Resumen

| Bloque | Estado | Filas |
|--------|--------|------:|
| Catálogos (fuentes, variables, cacao, requisitos, enfermedades, umbrales, fenología, escenarios, estrategias) | **Real / referencial** — ya en Supabase (migraciones 0001–0006) | ~90 |
| Territorio (país, 6 provincias, 85 cantones) | **Real** (geoBoundaries / INEC) | 92 |
| El Niño (ONI y 4 regiones Niño, 1990–2026) + 24 eventos | **Real** (NOAA CPC) | 2 209 + 24 |
| Clima mensual y conteos de peligro, 2001–2025 | **Real** (ERA5 vía Open-Meteo) | 11 280 + 2 820 |
| Riesgo de enfermedad por mes y por escenario | **Calculado** con los umbrales (por validar) | 8 460 + 648 |
| Aptitud ECOCROP por provincia | **Calculada** (ver aviso de sesgo de lluvia) | 6 |
| Producción nacional de cacao 2001–2024 | **Real** (FAOSTAT) | 24 |
| Producción provincial 2001–2024 | **SINTÉTICA** | 144 |
| Hectáreas por provincia y cantón | **SINTÉTICAS** | 91 |
| Precio internacional del cacao, mensual (2001–2026) | **Real** (FMI vía FRED) | 309 |
| Observaciones de moniliasis / escoba de bruja | **Real** (GBIF) | 12 |
| Modelo y predicciones de pérdida | **DEMO** (fórmula fija, no entrenado) | 1 + 182 |

## 2. Detalle por fuente

| Dato | Fuente | Licencia / cita | Cobertura cargada |
|------|--------|-----------------|-------------------|
| Límites | geoBoundaries gbOpen ECU ADM1/ADM2 (INEC, OCHA ROLAC), versión 2019, simplificados | CC BY 3.0 IGO | 6 provincias costeras y 85 cantones (se omiten las que no son de la Costa) |
| El Niño | NOAA CPC: `oni.ascii.txt` y `sstoi.indices` | Dominio público | ONI, Niño 1+2, 3, 3.4 y 4 desde 1990 (último mes: oct-2026) |
| Clima | Open-Meteo Historical API, modelo `era5_seamless` (ERA5 + ERA5-Land) | CC BY 4.0 + Copernicus | Provincias: diario 2001–2025. Cantones: ene–jun de 2020 (neutro) y 2025 (Niño) |
| Producción nacional | FAOSTAT `QCL`, *Cocoa beans*, Ecuador | CC BY 4.0 | Área cosechada, producción, rendimiento 2001–2024 |
| Precio | FRED `PCOCOUSDM` (precio mundial del cacao, USD/t) | FMI | 2001–2026, mensual (309 meses cargados) |
| Observaciones | GBIF, *Moniliophthora roreri* y *M. perniciosa*, Ecuador, con coordenadas | CC BY / CC0 según registro | 12 de 42 (los demás no traen fecha) |

Variables climáticas guardadas por área y mes: temperatura media, humedad relativa media,
lluvia total y humedad del suelo (0–7 cm), más los conteos de `area_monthly_hazard`
(días con lluvia ≥ 1 mm, ≥ 50 mm, racha lluviosa, días húmedos ≥ 80 %, días > 32 °C, días de
suelo saturado ≥ 0,45 m³/m³).

## 3. Datos sintéticos — cómo se generaron

| Dato | Método | Para qué sirve |
|------|--------|----------------|
| Producción provincial | Rendimiento = tendencia lineal nacional (FAOSTAT) × factor de provincia (0,9–1,1) × ruido × (1 − pérdida sembrada), donde la pérdida sembrada crece con el riesgo de enfermedad del año (hasta 40 %). Área cosechada = área nacional × reparto **supuesto** (Guayas 27 %, Los Ríos 22 %, Manabí 21 %, Esmeraldas 10 %, El Oro 5 %, Santo Domingo 4 %) | Probar `v_training_area_year` y el entrenamiento: **la señal clima → pérdida está plantada**, así que el modelo la "encontrará" por construcción |
| Hectáreas por cantón | Hectáreas de la provincia repartidas por superficie del cantón | Probar `crop_exposure` y el mapa |
| Modelo demo | `loss = clip(10 + 150 × (riesgo ene–jun − riesgo medio del área), 0, 60)` | Probar `loss_predictions` y `v_loss_map` |

Se marcan con `source_id = 'seed_sintetico'`, texto "SINTÉTICO" en `notes` y modelo
`cacao_loss_demo_sintetico`.

## 4. Hallazgos de calidad (importantes antes de usar los datos reales)

1. **El riesgo de moniliasis casi no discrimina.** Con la regla *HR media diaria ≥ 80 % y
   20–28 °C*, el 58 % de los meses por área tiene índice ≥ 0,95 (media 0,80). En la Costa
   esa condición se cumple casi todos los días. La mazorca negra sí varía (media 0,59; solo 17 %
   ≥ 0,95). **Acción:** subir el umbral de HR, usar horas de humedad (ERA5 horario) o contar
   rachas de días favorables en lugar de días sueltos; validar con el INIAP.
2. **ERA5 sobreestima la lluvia en la Costa.** Por ejemplo Los Ríos suma ≈ 5 400 mm/año y
   un punto de Esmeraldas ≈ 7 000 mm, contra el rango óptimo del cacao de 1 200–3 000 mm. Por eso
   la aptitud sale "marginal" o "no apta" en zonas que sí producen cacao. Para el MVP conviene
   calibrar con GPM IMERG (NASA) o con estaciones del INAMHI.
3. **Años Niño 2001–2025 según la regla anual** (ONI ≥ 0,5 o Niño 1+2 ≥ 0,4, promedio ene–jun):
   2010, 2015, 2016, 2017 (costero), 2019, 2023, 2024, 2025. Niña: 2008, 2011, 2021, 2022. **1997–98
   no entra** porque el clima empieza en 2001.
4. **Niño costero:** la regla de eventos solo detectó 2006; 2017 sí aparece como Niño costero en
   `v_enso_year_class`. Revisar el umbral de duración (4 meses) con un experto.
5. **Pocos años de entrenamiento:** 24 años × 6 provincias = 144 filas, 8 años Niño. Intervalos amplios.
6. **GBIF:** solo 12 observaciones con fecha; sirven para validar espacialmente, no para entrenar.
7. **Elevación:** `elevation_mean_m` es la altitud del punto representativo (la que informa
   Open-Meteo), no una media del polígono.
8. **Cantones con solo 2 años:** el escenario `normal`/`nino` de los cantones usa un solo año de
   cada tipo (2020 y 2025), no un compuesto.

## 5. Lo que falta para reemplazar lo sintético y lo referencial

| Pendiente | Cómo | Quién |
|-----------|------|-------|
| Producción **real** por provincia (ESPAC) | Descargar los tabulados anuales del INEC → `crop_production_stats` con `source_id = 'espac'` (y rellenar `areas.inec_dpa_code` de cantones) | Datos |
| Hectáreas reales por cantón | ESPAC (si publica por cantón) o cobertura WorldCover + censo | Datos |
| Precio **Ecuador** (grano seco) | SIPA / MAG; hoy solo hay el precio internacional | Datos |
| Códigos DPA de los 85 cantones | Tabla de códigos del INEC | Datos |
| Clima NASA (GPM, SMAP, MODIS) | ETL con Earth Engine; hoy el clima es ERA5 | Backend |
| Suelo (pH, arcilla, carbono), pendiente, cobertura | OpenLandMap, SRTM, WorldCover → `area_static_features` | Datos |
| Proyecciones 2050 | NEX-GDDP-CMIP6 → `area_scenario_climate` (escenarios `ssp245_2050`, `ssp585_2050`) | Fase 2 |
| Reducciones de las estrategias y costos | Literatura / INIAP → `strategy_effects`, `adaptation_strategies.cost_usd_ha_year` | Agrónomo |
| Validar umbrales de enfermedad, ventana de riesgo y umbrales de ENSO | INIAP / fitopatólogo / INAMHI → `validated = true` | Agrónomo |
| Entrenar el modelo real | `ml/train.py` sobre `v_training_area_year` (ver [05](05-modelo-predictivo.md)) | ML |

## 6. Cómo se verificó el seed

- Los 6 archivos se generan con `build_seed.py` y se revisó a mano una muestra.
- Una versión mínima (primeras filas de cada tabla) se ejecutó en Supabase dentro de una
  transacción con *rollback*: **todas las tablas aceptaron las filas**, `v_loss_map`,
  `v_enso_year_class` y `v_training_area_year` devolvieron datos, y las sentencias de `--reset` son
  válidas. Esa prueba encontró y corrigió dos fallos del generador (formato del JSON de
  `top_factors` y una fórmula demo que daba "muy alto" en todas partes).
- **Carga completa ejecutada el 2026-11-14 en el proyecto de Supabase** con `inject.py`
  (6 partes en ~6 s). Antes se probó el volumen completo en una transacción con *rollback*, lo
  que detectó 3 polígonos inválidos (islotes con < 4 puntos) y llevó a reparar la geometría con
  `st_makevalid` al insertar. Después se probó `--reset` y la recarga (92 áreas, 182 predicciones),
  se confirmó que `anon` lee pero no escribe, que no quedan filas huérfanas tras el borrado en
  cascada, y que el revisor de seguridad de Supabase no reporta alertas.
