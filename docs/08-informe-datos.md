# 8. Informe de datos — qué hay cargado, de dónde sale y qué falta

Actualizado: 2026-11-14 (carga con **solo datos reales**). Archivos: [`supabase/seed/`](../supabase/seed/README.md).
Cómo conseguir lo que falta: [09](09-como-conseguir-los-datos-que-faltan.md). Producción ESPAC: [10](10-espac-produccion-real.md).

> **No hay ningún dato sintético en la base.** Se eliminaron la producción sintética, las hectáreas
> inventadas por cantón y el modelo demo con sus predicciones. Lo que no tiene dato real quedó **vacío**.

## 1. Lo cargado en Supabase

| Bloque | Fuente | Filas |
|--------|--------|------:|
| Catálogos (fuentes, variables, cacao, requisitos, enfermedades, umbrales, fenología, escenarios, estrategias) | Referencial (migraciones 0001–0009) | ~90 |
| Territorio: Ecuador, **12 provincias** (6 Costa + 6 Amazonía), **126 cantones** | geoBoundaries / INEC | 139 |
| Códigos DPA: 12/12 provincias, 124/126 cantones | HDX COD-AB (INEC) | — |
| El Niño: ONI y regiones Niño 1+2, 3, 3.4, 4 (1990–oct 2026) + 24 eventos | NOAA CPC | 2 209 + 24 |
| Clima mensual (11 variables) | ERA5 vía Open-Meteo | 84 546 |
| Conteos de peligro mensuales (días de lluvia, aguacero, calor, humedad, suelo saturado) | Calculado del clima | 7 686 |
| Altitud, pendiente (SRTM) y suelo (SoilGrids) | OpenTopoData, ISRIC | 138 |
| Riesgo de enfermedad por mes / por escenario | Calculado con umbrales **por validar** | 23 058 + 5 832 |
| Aptitud ECOCROP (provincias) | Calculada | 12 |
| **Producción de cacao por provincia 2002–2025** | **ESPAC (INEC)** | 220 |
| Producción nacional | ESPAC 2002–2025 (24) + FAOSTAT 2001–2024 (24) | 48 |
| Superficie cosechada por provincia (2025) | ESPAC | 12 |
| Precio internacional del cacao, 2001–2026 | FRED (FMI) | 309 |
| Observaciones de moniliasis / escoba de bruja | GBIF | 12 |

**Vacías a propósito** (no hay dato real): hectáreas por cantón, `model_versions`, `training_samples`,
`loss_predictions`, `strategy_evaluations`, `zone_classification`, `field_profiles`, `strategy_reviews`.

## 2. Fuentes

| Dato | Fuente | Licencia / cita | Cobertura |
|------|--------|-----------------|-----------|
| Límites | geoBoundaries gbOpen ECU ADM1/ADM2 (INEC, OCHA ROLAC), v2019 | CC BY 3.0 IGO | 12 provincias y 126 cantones |
| Códigos DPA | HDX COD-AB Ecuador `ecu_admgz.xlsx` | CC BY-IGO | 5 nombres abreviados se asignaron a mano |
| El Niño | NOAA CPC `oni.ascii.txt`, `sstoi.indices` | Dominio público | 1990–oct 2026 |
| Clima | Open-Meteo Historical, `era5_seamless` | CC BY 4.0 + Copernicus | Provincias 2001–2025; cantones ene–jun de 2018, 2020, 2023, 2024, 2025 y 2016 (51 de 126) |
| Altitud / pendiente | SRTM 30 m vía OpenTopoData | NASA SRTM | 16 puntos por polígono |
| Suelo | SoilGrids v2 (ISRIC), 0–30 cm | CC BY 4.0 | 133 de 138 áreas |
| Producción por provincia | **ESPAC (INEC)**, tabulados anuales de cacao (almendra seca), solo + asociado | INEC | 2002–2025; las provincias suman el total nacional (±2 %) en los 24 años |
| Producción nacional | FAOSTAT `QCL` | CC BY 4.0 | 2001–2024 |
| Precio | FRED `PCOCOUSDM` | FMI | 2001–sep 2026 |
| Observaciones | GBIF | CC BY / CC0 | 12 de 42 (los demás no traen fecha) |

## 3. Hallazgos de calidad

1. **El riesgo de moniliasis casi no discrimina:** con *HR media diaria ≥ 80 % y 20–28 °C*, el 58 % de los
   meses por área sale ≥ 0,95. La mazorca negra sí varía. Ajustar con el INIAP.
2. **ERA5 sobreestima la lluvia en la Costa y la Amazonía** (Los Ríos ≈ 5 400 mm/año contra un óptimo de
   1 200–3 000): la aptitud sale "marginal/no apta" donde sí se produce. Calibrar con GPM IMERG o INAMHI.
3. **Años Niño 2001–2025:** 2010, 2015, 2016, 2017 (costero), 2019, 2023, 2024, 2025. Niña: 2008, 2011, 2021, 2022.
4. **El rendimiento reportado por ESPAC sube mucho en el tiempo** (≈ 0,07–0,11 t/ha en 2002 contra 0,4–1,0 en
   2025): hay que **quitar la tendencia por provincia** antes de modelar (ver [05](05-modelo-predictivo.md)).
5. **Amazonía:** el INEC publicó esas provincias agregadas (Nororiente / Centro-Suroriente) hasta 2011; sus filas
   empiezan en 2012. Santo Domingo empieza en 2009 (provincia creada en 2007).
6. **2001 no tiene producción por provincia** (ESPAC empieza en 2002); solo hay el dato nacional de FAOSTAT.
7. **Cantones con pocos años de clima y sin hectáreas:** no tienen producción ni pérdida estimada; solo riesgo
   climático (escenarios normal y Niño, sin Niña).
8. **Sierra fuera de alcance:** Bolívar, Cañar, Pichincha y Cotopaxi tienen cacao (están en el CSV de ESPAC)
   pero no en `areas`.
9. **Altitud:** hay cantones por encima de 900 m (óptimo máximo del cacao en ECOCROP).
10. **GBIF:** 12 observaciones con fecha; 2 caen fuera de los cantones cargados (sin territorio).

## 4. Lo que todavía falta

| Pendiente | Cómo | Quién |
|-----------|------|-------|
| **Entrenar el modelo real** (ya hay 220 filas reales en `v_training_area_year`) | [05](05-modelo-predictivo.md) → `model_versions`, `loss_predictions` | ML |
| Clima de cantones restante (2016, 2015, 2022, 2014) | Relanzar `fetch_weather.py` (límite diario de Open-Meteo) | Datos |
| Hectáreas de cacao por cantón (dato real) | Censo agropecuario / mapas de cobertura; hoy no hay | Datos |
| Precio del cacao en Ecuador | SIPA / MAG (sin descarga automática) | Datos |
| Clima NASA (GPM, SMAP, MODIS) y cobertura | ETL con Earth Engine | Backend |
| Proyecciones 2050 | NEX-GDDP-CMIP6 | Fase 2 |
| Reducciones de las estrategias y costos | Literatura / INIAP | Agrónomo |
| Validar umbrales de enfermedad, ventana de riesgo y umbral de Niño costero | INIAP / fitopatólogo / INAMHI | Agrónomo |

## 5. Cómo se verificó

- **Prueba completa con rollback** antes de cargar (≈ 11 MB de SQL, 7 partes): 139 polígonos válidos;
  `v_training_area_year` = **220 filas completas, 2002–2025, 12 provincias**; **0 filas sintéticas**.
- **Control de ESPAC** (Emilio Cuenca, [10](10-espac-produccion-real.md)): provincias + agregados no
  provinciales = total nacional (±2 %) en los 24 años; se revisó el SQL antes de ejecutarlo.
- **Carga real** con `inject.py --reset --yes` (7 partes, ~12 s); revisor de seguridad de Supabase: **0 alertas**.
- **Auditoría de consistencia** en SQL: sin huérfanos ni duplicados; 12 provincias con riesgo 2001–2025.
