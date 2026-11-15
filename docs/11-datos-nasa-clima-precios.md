# 11. Datos que faltaban: clima de cantones, NASA satelital, proyecciones 2050 y precios

Fecha: 2026-11-14. Resuelve los puntos 1, 3 (parcial), 6 y 7 de [09](09-como-conseguir-los-datos-que-faltan.md).
Archivos de inyección: `supabase/seed/data/08_…sql` a `11_…sql` (**no aplicados todavía**).

| Parte | Qué trae | Fuente | Destino |
|-------|----------|--------|---------|
| **08** `08_clima_cantones.sql` | Clima ene–jun de cantones: **2014, 2015, 2022** (126 cantones) y **2016** (los 75 que faltaban) + escenarios normal / Niño / **Niña** de todos los cantones | Open-Meteo `era5_seamless` | `area_monthly_series`, `area_monthly_hazard`, `disease_risk_monthly`, `area_scenario_climate`, `disease_risk_scenario` |
| **09** `09_nasa_satelital.sql` | NDVI, anomalía de NDVI, temperatura de superficie, evapotranspiración, humedad del suelo (SMAP, GLDAS), **lluvia GPM IMERG**, cobertura del suelo — media sobre el **polígono** de las 138 áreas, 2001–2025 | NASA vía Google Earth Engine | `area_monthly_series`, `area_static_features.land_cover`, `variables` (+`precip_gpm`) |
| **10** `10_proyecciones_2050.sql` | Clima, **riesgo de enfermedad**, aptitud y matriz de zonas para 2041–2060 (SSP2-4.5 y SSP5-8.5) | NASA NEX-GDDP-CMIP6 vía Earth Engine | `area_scenario_climate`, `disease_risk_scenario`, `crop_suitability`, `zone_classification` |
| **11** `11_precios_ecuador.sql` | Precio al productor de cacao **en Ecuador**: mensual 2012–2022, anual 1991–2024 | FAOSTAT | `crop_prices` |
| **12** `12_precio_sipa.sql` | Precio al productor **SIPA (MAG)** mensual 2014–2024 (130 meses) | Fichas de cacao de SIPA (PDF) | `crop_prices` (`nacional`) |

## Resultado

| Parte | Tamaño | Filas |
|-------|-------:|-------|
| 08 | 3,2 MB | cantones × año: 2014 = 126, 2015 = 126, 2016 = 75, 2022 = 126 (series, peligros y riesgo mensual) + escenarios recalculados |
| 09 | 21,4 MB | `ndvi` 40 470 · `ndvi_anom` 40 470 · `lst_day` 40 706 · `et_actual` 41 400 · `soil_moisture_long` 41 400 · `soil_moisture_root` 17 802 · `precip_gpm` 40 986 · `land_cover` 138 áreas |
| 10 | 163 KB | 864 deltas de clima + 864 de riesgo (12 provincias × 2 escenarios × 12 meses × 3), aplicados a provincias y cantones en SQL |
| 11 | 13 KB | 129 meses + 34 años |

Todas las partes pasan el parser de Postgres (`pglast`) y `inject.py --dry-run`. GPM IMERG mensual aún no publica
oct–dic 2025 (retraso de la NASA): esos meses quedan sin dato.

## Cómo regenerar e inyectar

```bash
# Requisitos: BACK/venv con earthengine-api, shapely, openpyxl; `earthengine authenticate`; GEE_PROJECT en BACK/.env
R=supabase/seed/raw
python -I supabase/seed/tools/fetch_weather_missing.py $R     # 08: Open-Meteo, solo cantón × año que no están en la BD
python -I supabase/seed/tools/fetch_gee.py $R                 # 09: Earth Engine (~15 min)
python -I supabase/seed/tools/fetch_cmip6_gee.py $R           # 10: Earth Engine (~4 min)
curl -L -o $R/faostat_prices.zip https://bulks-faostat.fao.org/production/Prices_E_Americas.zip   # 11
python -I supabase/seed/tools/build_extra.py $R supabase/seed/data          # genera 08–11 (no toca la base)

python -I supabase/seed/tools/sipa_fichas.py $R/sipa/ficha $R/sipa_cacao.csv   # 12: fichas SIPA exportadas a mano
python supabase/seed/inject.py --only 8,9,10,11,12            # requiere SUPABASE_DB_URL; después de 01–07
```

Insumos comunes en `supabase/seed/raw/` (no versionado): `adm1.geojson`, `adm2.geojson` (geoBoundaries, mismas
URL que `download_raw.py`), `oni.txt`, `sstoi.txt` (NOAA) y `areas.json` (puntos y claves de cada área,
generados con `build_areas()` de `fetch_weather.py`). Los ids de área se reconstruyen con el mismo
UUID5 que `build_seed.py`: **138/138 coinciden** con el seed.

---

## 08 · Clima de cantones (Open-Meteo)

- **Qué faltaba** (consultado en la BD): 2016 solo tenía 51 de 126 cantones; 2014, 2015 y 2022 no tenían ninguno.
- **Descarga:** `tools/fetch_weather_missing.py` reutiliza `fetch()` de `fetch_weather.py` (mismas variables
  diarias, `era5_seamless`, ene–jun, caché en `raw/weather/`). **453/453 descargas sin error** con la cuota diaria
  de esta máquina (la cuota de Open-Meteo es por IP).
- **Proceso:** copia exacta de `month_stats` y `RULES` de `build_seed.py` → mismas columnas y umbrales.
  `on conflict do nothing`: no pisa lo ya cargado.
- **Escenarios:** el archivo **recalcula en SQL** `area_scenario_climate` y `disease_risk_scenario` de los
  cantones (normal / Niño / Niña) con todo lo que haya en `area_monthly_hazard` y `disease_risk_monthly`, usando la
  regla única `v_enso_year_class`. Con 2022 aparece por primera vez el escenario **Niña** en cantones.

## 09 · NASA satelital por Earth Engine

Proyecto GEE: `proyectito-uwu-514715`. Script: `tools/fetch_gee.py`. Polígonos: los mismos que
`build_seed.py` (provincia = ADM1; cantón = ADM2 cuyo punto representativo cae en su provincia), simplificados a ~300 m.

| Variable | Colección GEE | Cálculo | Periodo |
|----------|---------------|---------|---------|
| `ndvi` | `MODIS/061/MOD13Q1` | media del mes, píxeles con `SummaryQA ≤ 1` (sin nube), × 0.0001 | 2001–2025 |
| `ndvi_anom` | (derivada) | NDVI − media del mismo mes en el área | 2001–2025 |
| `lst_day` | `MODIS/061/MOD11A2` | `LST_Day_1km` × 0.02 − 273.15 (°C) | 2001–2025 |
| `et_actual` | `MODIS/061/MOD16A2GF` | media(`ET` × 0.1) / 8 × días del mes (mm/mes) | 2001–2025 |
| `soil_moisture_root` | `NASA/SMAP/SPL4SMGP/008` | media de `sm_rootzone` (m³/m³) | 2015-04–2025 |
| `soil_moisture_long` | `NASA/GLDAS/V021/NOAH/G025/T3H` | media de `RootMoist_inst` (kg/m²) | 2001–2025 |
| **`precip_gpm`** (nueva) | `NASA/GPM_L3/IMERG_MONTHLY_V07` | mm/h × 24 × días del mes | 2001–2025 |
| `land_cover` | `ESA/WorldCover/v200` (2021) | fracción de cada clase en el polígono | estático |

**`precip_gpm` es una variable nueva** porque la variable `precip` cargada hoy viene de ERA5 (Open-Meteo),
aunque el catálogo la atribuye a GPM. Diferencia importante: en **Los Ríos 2024, GPM da ~1 490 mm/año y ERA5
~5 400 mm**. GPM cae dentro del óptimo del cacao (1 200–3 000 mm); ERA5 lo saca de rango. Recomendación:
usar `precip_gpm` para la aptitud ECOCROP (ver [08](08-informe-datos.md) § 4.2).

## 10 · Proyecciones 2050 (NASA NEX-GDDP-CMIP6)

Script: `tools/fetch_cmip6_gee.py` (Earth Engine `NASA/GDDP-CMIP6`, todo se calcula en el servidor de Google).

- **Modelos:** ACCESS-CM2, EC-Earth3, GFDL-ESM4, MRI-ESM2-0 (r1i1p1f1), los del plan ([APIS-DATOS](APIS-DATOS.md) § 15).
- **Periodos completos:** histórico **1995–2014** y futuro **2041–2060**, SSP2-4.5 y SSP5-8.5 (≈ 600 días por mes y periodo).
- Por provincia (media sobre el polígono), modelo, periodo y mes: temperatura media (`tas`), humedad (`hurs`),
  lluvia (`pr`) y **fracción de días favorables** a cada enfermedad con la regla diaria de `disease_thresholds`.
- **Método delta:** cambio = futuro − histórico **del mismo modelo** (así se cancela el sesgo de cada modelo);
  temperatura y humedad en valor absoluto, lluvia en %. Se aplica al clima **normal observado** de cada provincia
  y de sus cantones. Se guarda la media de los 4 modelos y el rango (mín–máx) como incertidumbre.
- **Riesgo de enfermedad 2050** = riesgo normal observado + cambio de días favorables, recortado a 0–1.
- **Aptitud ECOCROP futura** (provincias) con la misma función `part_score` de `build_seed.py`.
- **Matriz de zonas** (provincias): segura / manejo / transición / crítica, con aptitud ≥ 0,6 y riesgo
  medio ene–jun 2050 ≥ 0,6 como cortes. **Cortes por validar.**

Resultado ilustrativo — Los Ríos, febrero, SSP5-8.5: **+1,5 °C** (1,1–1,9 entre modelos), lluvia **+10 %**
(−3 a +35 %) y **−40 puntos** de días favorables a moniliasis: más días superan su máximo térmico de 28 °C.
La mazorca negra baja menos. Ojo: esto depende de los umbrales, que aún no están validados.

Limitaciones: hereda el sesgo de lluvia de ERA5 (el delta se suma a ERA5); en meses secos el cambio de lluvia en %
es muy variable entre modelos (base casi cero); cantones heredan el delta de su provincia (celdas de ~27 km).

## 11 · Precio en Ecuador (FAOSTAT)

FAOSTAT *Producer Prices* (`bulks-faostat.fao.org/production/Prices_E_Americas.zip`), Ecuador, *Cocoa beans*.
Ecuador está dolarizado (moneda local = USD).
- `market = 'productor_faostat'`: **mensual 2012–2022** (129 meses).
- `market = 'productor_faostat_anual'`: **anual 1991–2024** (34 años; guardado en el 1 de enero).

## 12 · Precio al productor SIPA (MAG)

SIPA no tiene descarga directa: los datos se exportaron **a mano** desde
https://sipa.agricultura.gob.ec/index.php/cacao (botón de descarga del tablero) y se dejaron en
`supabase/seed/raw/sipa/` (no versionado):

| Archivo exportado | Qué trae | ¿Se usa? |
|-------------------|----------|----------|
| `FICHA_CACAO*.pdf` (15 fichas, una por año 2010–2024) | Gráfico **"Precio Productor"** con los 12 valores mensuales impresos (USD por quintal) | ✅ parte 12 |
| `TAB_PP_data*.csv` (9 archivos) | Precio al productor **por provincia** (USD/qq): mes actual, mes anterior, mismo mes del año anterior | ❌ **no traen la fecha**: falta saber a qué mes corresponde cada archivo |
| `TBL_PP.pdf` | Tabla por provincia, CCN-51, **septiembre 2016** (una sola foto) | Solo para validar |
| `precios_mayoristas_2026.pdf` | Boletín de precios mayoristas, sept. 2026 | ❌ no incluye cacao |

**Cómo se leyeron las fichas** (`tools/sipa_fichas.py`): `pdftotext -bbox` da la posición de cada palabra; cada
valor `$ 123.45` se asigna al mes cuya etiqueta (ENERO … DICIEMBRE) está más cerca en horizontal. Cuando el tablero
recorta etiquetas (SEPTIEMBRE, NOVIEMBRE, DICIEMBRE en las fichas de una página), su posición se estima con una
recta (los meses están equiespaciados). Si dos valores caen en el mismo mes, la ficha se descarta.

| Resultado | |
|-----------|--|
| Meses cargados | **130** (2014–2024) |
| 2010–2013 | el gráfico de SIPA está **vacío** (sin dato) |
| 2019 | **10 meses** (el tablero muestra solo 10 valores) |
| Conversión | USD/qq × 1000 / 45,36 = USD/t (1 qq = 100 lb), igual que `build_seed.py` |
| Destino | `crop_prices`, `market = 'nacional'`, `source_id = 'sipa'` → lo usa el modelo demo |
| Control | ene-2020: SIPA 109 USD/qq vs FAOSTAT 2 404 USD/t (= 109 USD/qq). sept-2016 nacional 114 vs Los Ríos 113 (TBL_PP) |
| Ejemplo | 2024: 153 USD/qq en enero → **394 en abril** (máximo histórico) → 360 en diciembre |

CSV versionado: [`supabase/seed/data/sipa_precio_productor_cacao.csv`](../supabase/seed/data/sipa_precio_productor_cacao.csv).

## Lo que sigue pendiente

| Pendiente | Por qué | Cómo |
|-----------|---------|------|
| Precio SIPA **por provincia** | Los `TAB_PP_data*.csv` exportados no traen la fecha | Volver a exportar indicando mes/año (o anotar a qué mes es cada archivo) |
| `et0`, `water_balance` | Necesitan radiación y viento diarios (FAO-56) | Open-Meteo `et0_fao_evapotranspiration` o ERA5-Land en GEE |
| `esi` (ECOSTRESS) | Requiere cuenta Earthdata (AppEEARS) | [APIS-DATOS](APIS-DATOS.md) § 16 |
| `rh2m`, `solar_rad` (NASA POWER) | No priorizado (ya hay `rh_mean` de ERA5) | API POWER sin cuenta |
| Validar umbrales, cortes de zonas y estrategias | Requiere experto | INIAP / fitopatólogo |
| Usar `precip_gpm` en la aptitud | Decisión del equipo de datos | Recalcular `crop_suitability` con GPM |
