# Seed de pruebas — CacaoResiliente

Datos para **probar la base de datos y el backend** sin esperar al ETL real:
92 áreas con polígono (Ecuador, 6 provincias de la Costa, 85 cantones), El Niño 1990–2026,
clima diario 2001–2025 resumido por mes, índices de riesgo, producción, precios, un modelo
**DEMO** y sus predicciones. Qué es real y qué es sintético: [`docs/08-informe-datos.md`](../../docs/08-informe-datos.md).

> ⚠️ Contiene datos **sintéticos** (producción provincial, hectáreas por cantón, modelo y
> predicciones demo). Están marcados (`source_id = 'seed_sintetico'`, `notes`, modelo
> `cacao_loss_demo_sintetico`). **No los presentes como resultados.**

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
`data/seed_completo.sql` es la concatenación de las 6 partes (para `psql -f`).

## Contenido de `data/`

| Parte | Tablas | Filas |
|-------|--------|------:|
| 01_territorio | `areas`, `area_static_features`, `data_sources` (+4 fuentes) | 92 + 91 + 4 |
| 02_el_nino | `enso_index`, `enso_events` | 2 209 + 24 |
| 03_clima | `area_monthly_series`, `area_monthly_hazard` | 11 280 + 2 820 |
| 04_riesgo_y_escenarios | `disease_risk_monthly`, `area_scenario_climate`, `disease_risk_scenario`, `crop_suitability` | 8 460 + 648 + 648 + 6 |
| 05_produccion_y_precios | `crop_production_stats`, `crop_exposure`, `crop_prices` | 168 + 91 + 309 |
| 06_modelo_demo_y_observaciones | `model_versions`, `loss_predictions`, `field_observations`, `etl_runs` | 1 + 182 + 12 + 1 |

## Probar después de cargar

```sql
-- Mapa: pérdida demo por cantón
select name, province, scenario_id, loss_pct, risk_class from public.v_loss_map order by loss_pct desc limit 10;
-- Años Niño / Niña / neutro
select year, enso_class, is_coastal_nino from public.v_enso_year_class order by year desc limit 10;
-- Dataset de entrenamiento (provincia × año)
select area_id, year, yield_t_ha, fav_days_phytophthora, enso_class from public.v_training_area_year limit 10;
```

## Regenerar los datos desde cero

```bash
cd supabase/seed/tools
python download_raw.py  <carpeta_raw>              # límites, NOAA, FRED, FAOSTAT, GBIF
python fetch_weather.py <carpeta_raw>              # clima diario ERA5 (Open-Meteo), ~15 min
python build_seed.py    <carpeta_raw> ../data      # genera los .sql
python build_seed.py    <carpeta_raw> ../data_muestra --sample   # versión mínima de prueba
```

El clima se guarda en caché (`<raw>/weather/`): se puede relanzar sin repetir llamadas.
Open-Meteo gratuito limita las peticiones; el script espera y reintenta solo.

## Cuando lleguen los datos reales

Reemplazar, no mezclar: `python inject.py --reset-only`, y cargar con el ETL real. Las filas
del seed se reconocen por `source_id = 'seed_sintetico'`, el modelo `cacao_loss_demo_sintetico`
y los ids de `areas` generados por UUID5 (reproducibles).
