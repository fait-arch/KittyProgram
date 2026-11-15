# Seed de pruebas — CacaoResiliente

Datos para **probar la base de datos y el backend** sin esperar al ETL real:
139 áreas con polígono (Ecuador, 12 provincias de Costa y Amazonía, 126 cantones), El Niño 1990–2026,
clima mensual, altitud/pendiente/suelo, índices de riesgo, **producción real de ESPAC 2002–2025 por provincia**,
precios y observaciones de campo. Qué hay cargado, de dónde sale y qué falta: [`docs/08-informe-datos.md`](../../docs/08-informe-datos.md).

> ✅ **Solo datos reales.** No hay datos sintéticos, modelo demo ni predicciones: se cargan cuando exista un
> modelo entrenado. Detalle: [`docs/08-informe-datos.md`](../../docs/08-informe-datos.md).

## Inyectar en Supabase (3 pasos)

```bash
# 1. Dependencias
pip install -r supabase/seed/requirements.txt

# 2. Conexión: Supabase → Project Settings → Database → Connection string → "Session pooler"
#    Guárdala en BACK/.env (ya está en .gitignore):
#    SUPABASE_DB_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres

# 3. Cargar
python supabase/seed/inject.py
```

Requisito: las migraciones 0001 → 0006 ya aplicadas.

| Comando | Qué hace |
|---------|----------|
| `python inject.py --dry-run` | Revisa los archivos sin conectarse |
| `python inject.py` | Carga las 6 partes (cada una en su transacción) |
| `python inject.py --reset` | Borra el seed y lo vuelve a cargar |
| `python inject.py --reset-only` | Solo borra el seed |
| `python inject.py --only 2,5` | Solo algunas partes |
| `python inject.py --verify` | Muestra los conteos de cada tabla |

Si no quieres usar Python: pega los archivos de `data/` **en orden** en el SQL Editor de
Supabase (01 → 06). El 03 pesa ~1,1 MB; si el editor lo rechaza, usa `inject.py`.
`build_seed.py` también genera `data/seed_completo.sql` (concatenación de las 6 partes, para `psql -f`), pero **no se versiona** (pesa ~10 MB).

## Contenido de `data/`

| Parte | Tablas | Filas |
|-------|--------|------:|
| 01_territorio | `areas`, `area_static_features`, `data_sources` (+5 fuentes) | 139 + 138 + 5 |
| 02_el_nino | `enso_index`, `enso_events` | 2 209 + 24 |
| 03_clima | `area_monthly_series`, `area_monthly_hazard` | 84 546 + 7 686 |
| 04_riesgo_y_escenarios | `disease_risk_monthly`, `area_scenario_climate`, `disease_risk_scenario`, `crop_suitability` | 23 058 + 5 832 + 5 832 + 12 |
| 05_produccion_y_precios | `crop_production_stats` (FAOSTAT nacional), `crop_exposure`, `crop_prices` | 24 + 12 + 309 |
| 06_observaciones | `field_observations`, `etl_runs` | 12 + 1 |
| 07_espac_real | `crop_production_stats` (ESPAC por provincia y nacional) | 220 + 24 |

## Probar después de cargar

```sql
-- Producción real por año y fuente
select * from public.v_production_provenance order by year desc limit 10;   -- v_loss_map estará vacía hasta entrenar el modelo real
-- Años Niño / Niña / neutro
select year, enso_class, is_coastal_nino from public.v_enso_year_class order by year desc limit 10;
-- Dataset de entrenamiento (provincia × año)
select area_id, year, yield_t_ha, fav_days_phytophthora, enso_class from public.v_training_area_year limit 10;
```

## Regenerar los datos desde cero

```bash
cd supabase/seed/tools
python download_raw.py  supabase/seed/raw              # límites, DPA, NOAA, FRED, FAOSTAT, GBIF, ESPAC 2023-2025
python fetch_weather.py supabase/seed/raw              # clima diario ERA5 (Open-Meteo), varias horas
python fetch_static.py  supabase/seed/raw              # altitud/pendiente (SRTM) y suelo (SoilGrids), ~1 h
python build_seed.py    supabase/seed/raw ../data      # genera los .sql
python build_seed.py    supabase/seed/raw ../data_muestra --sample   # versión mínima de prueba
```

Los tres pasos de descarga guardan caché en `<raw>/`: se pueden relanzar sin repetir llamadas.
**Open-Meteo gratuito tiene un límite diario**: si se agota, `fetch_weather.py` se detiene y se
retoma al día siguiente. SoilGrids permite ~5 peticiones/min.

## Qué falta y cómo conseguirlo

Ver [`docs/09-como-conseguir-los-datos-que-faltan.md`](../../docs/09-como-conseguir-los-datos-que-faltan.md).

## Recargar

Todo lo cargado es real. Para recargar desde cero: `python inject.py --reset --yes` (borra solo lo del seed;
los ids de `areas` son UUID5 reproducibles). El modelo y las predicciones se cargan cuando exista un modelo entrenado.
