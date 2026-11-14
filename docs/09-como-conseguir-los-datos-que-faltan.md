# 9. Cómo conseguir los datos que faltan

Guía paso a paso. Cada punto dice **qué falta, dónde está, cómo bajarlo, dónde guardarlo y cómo
meterlo en la base**. Los datos crudos viven en `supabase/seed/raw/` (ya está en el `.gitignore`).

## Antes de empezar

```bash
pip install -r supabase/seed/requirements.txt          # una vez
# BACK/.env debe tener SUPABASE_DB_URL=postgresql://postgres.<ref>:<CLAVE>@aws-0-us-east-2.pooler.supabase.com:5432/postgres
```

**Siempre se termina igual** (regenera todo y recarga en ~10 s):

```bash
python supabase/seed/tools/build_seed.py supabase/seed/raw supabase/seed/data
python supabase/seed/inject.py --reset --yes
```

**Para ver qué falta en cualquier momento**, pegar en el SQL Editor de Supabase:

```sql
select variable_id, status from public.v_variable_coverage order by status, variable_id;   -- variables con/sin datos
select kind, name, climate_years, production_real_years, has_soil from public.v_area_coverage where kind <> 'country' order by climate_years;
select * from public.v_production_provenance order by year desc;                          -- qué producción es real
```

Resumen de lo pendiente, de lo más fácil a lo más difícil:

| # | Falta | Dificultad | Quién |
|---|-------|-----------|-------|
| 1 | Clima de cantones: 2016 (75 cantones), 2015, 2022, 2014 | Fácil (solo esperar) | Cualquiera |
| 2 | ~~Producción real por provincia 2014–2022 (ESPAC)~~ ✅ 2002–2025, ver [10](10-espac-produccion-real.md) | Hecho | Datos |
| 3 | Precio del cacao en Ecuador (SIPA) | Media (descarga manual) | Datos |
| 4 | Validar umbrales de enfermedad y calendario | Media (requiere un experto) | Agrónomo |
| 5 | Efecto y costo de cada estrategia | Media (literatura / INIAP) | Agrónomo |
| 6 | Datos NASA: GPM, SMAP, MODIS, WorldCover | Difícil (Earth Engine + ETL) | Backend |
| 7 | Proyecciones 2050 (NEX-GDDP-CMIP6) | Difícil (Earth Engine + ETL) | Backend |
| 8 | Provincias de la Sierra con cacao | Media | Datos |
| 9 | Entrenar el modelo real | Depende de 2 | ML |

---

## 1. Clima de cantones que falta (2016, 2015, 2022, 2014)

**Por qué falta:** el servicio gratuito Open-Meteo tiene un límite diario y se agotó. Lo ya bajado
está guardado, así que el script retoma donde quedó.

```bash
python supabase/seed/tools/fetch_weather.py supabase/seed/raw      # relanzar al día siguiente; puede tardar horas
python supabase/seed/tools/build_seed.py supabase/seed/raw supabase/seed/data
python supabase/seed/inject.py --reset --yes
```

Lo que se gana: escenario **Niña** en cantones (2022) y escenarios más sólidos (más años por clase).
Comprobar: `select climate_years, count(*) from v_area_coverage where kind='canton' group by 1;`

---

## 2. Producción real por provincia 2014–2022 (ESPAC, INEC)

> ✅ **Hecho (2026-11-14):** ESPAC 2002–2025 descargada y convertida a `supabase/seed/data/07_espac_real.sql`
> (pendiente de inyectar con `inject.py --only 7`). Detalle y aviso de que **2001 no existe en ESPAC**:
> [10-espac-produccion-real.md](10-espac-produccion-real.md).

**Por qué importa:** hoy solo 2023–2025 son reales (36 filas). Con 2014–2022 habría ~144 filas reales
y se podría entrenar el modelo de verdad. Es **el dato más valioso que falta**.

1. Abrir https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/ y entrar a
   **"Información de años anteriores ESPAC"** (https://www.ecuadorencifras.gob.ec/informacion-de-anos-anteriores-espac/).
2. Elegir el año y descargar los **tabulados en Excel** (el archivo que contiene la tabla
   *"Superficie, producción y ventas, según región y provincia — cacao (almendra seca)"*).
3. Guardar cada uno como **`supabase/seed/raw/espac_tab<AÑO>.xlsx`** (por ejemplo `espac_tab2019.xlsx`).
4. Regenerar y recargar (comandos de arriba).

El generador lee solo los años cuyo archivo exista y **comprueba que las provincias sumen el total
nacional (±2 %)**; si un año no cuadra o tiene otro formato, lo avisa y lo omite en vez de cargar datos
malos. Los años con dato real reemplazan automáticamente a los sintéticos.

Comprobar: `select * from v_production_provenance where year between 2014 and 2022;` → `is_real = true`.

---

## 3. Precio del cacao en Ecuador (SIPA, MAG)

**Hoy:** solo el precio internacional (FMI). **Se necesita:** precio en Ecuador, grano seco.

1. Entrar a http://sipa.agricultura.gob.ec/ y buscar el reporte de **precios de cacao en almendra seca**.
2. Exportar la serie mensual (o copiarla a una hoja de cálculo).
3. Guardar como **`supabase/seed/raw/sipa_cacao.csv`** con este formato (una de las dos columnas de precio):

```csv
month,usd_per_qq
2023-01,98.5
2023-02,101.2
```

   `usd_per_qq` = USD por quintal (se convierte con 1 qq = 45,36 kg); si ya tienes USD por tonelada, usa la columna `usd_per_t`.
4. Regenerar y recargar. Quedan como `market = 'nacional'`, `source_id = 'sipa'` y el modelo demo usa
   estos precios en lugar de los internacionales.

---

## 4. Validar umbrales de enfermedad y calendario (experto)

Contactar al **INIAP** (Estación Experimental Tropical Pichilingue, Quevedo) o a un fitopatólogo.
Llevar las tablas `disease_thresholds` y `crop_phenology`. Cuando confirme o corrija:

```sql
-- Ejemplo: cambiar el umbral de humedad de la moniliasis a 85 % y marcarlo validado
update public.disease_thresholds
   set min_value = 85, validated = true, source_ref = 'INIAP — nombre del técnico, fecha'
 where pathogen_id = 'monilia' and variable_id = 'rh_mean';

update public.crop_phenology set validated = true, source_ref = 'INIAP — ...' where crop_id = 'cacao' and region = 'costa';
```

**Cambiar un umbral exige recalcular el riesgo** (`disease_risk_monthly`): hoy se calcula en
`build_seed.py` (`RULES`); actualizar ahí la misma regla y recargar. El umbral que más urge: la
moniliasis (casi no discrimina entre zonas con HR ≥ 80 %).

---

## 5. Efecto y costo de cada estrategia (literatura / INIAP)

Llenar `strategy_effects` (7 filas ya creadas, con `reduction_pct_*` vacío) y el costo:

```sql
update public.strategy_effects
   set reduction_pct_low = 30, reduction_pct_high = 60,
       source_ref = 'Autor, año, título (DOI)', validated = true
 where strategy_id = 'sanitario' and target = 'monilia';

update public.adaptation_strategies set cost_usd_ha_year = 120, source_ref = '...' where id = 'sanitario';
```

Con esto se puede generar `strategy_evaluations` (pérdida evitada y beneficio neto por zona).
**No inventar cifras**: si no hay fuente, dejar vacío y mostrar "sin datos".

---

## 6. Datos NASA: GPM, SMAP, MODIS y WorldCover (Earth Engine)

**Qué aportan:** lluvia calibrada (corrige el sesgo de ERA5), humedad del suelo real, NDVI (suelo
desnudo/estrés), temperatura de superficie y cobertura. Llenan las variables hoy pendientes:
`ndvi`, `ndvi_anom`, `lst_day`, `soil_moisture_root`, `soil_moisture_long`, `et_actual`, `et0`, `esi`…

1. Registrar el proyecto: https://code.earthengine.google.com/register → *Unpaid usage* → *Academia & Research* → crear proyecto Cloud (anotar el ID).
2. Instalar y autenticar (se abre el navegador; entrar con tu cuenta de Google):
   ```bash
   pip install earthengine-api
   earthengine authenticate
   ```
3. Poner `GEE_PROJECT=<tu-id>` en `BACK/.env`.
4. **Escribir el ETL** (`BACK/etl/etl_climate.py`): el código de ejemplo para cada fuente está en
   [APIS-DATOS.md](APIS-DATOS.md) y [BACK/docs/07-extraccion-datos.md](../BACK/docs/07-extraccion-datos.md).
   Escribe en `area_monthly_series` (mismas columnas que hoy) y se ve en `v_variable_coverage`.
   Pídeme que lo construya cuando GEE esté autenticado.

---

## 7. Proyecciones 2050 (NEX-GDDP-CMIP6)

Misma conexión a Earth Engine que el punto 6. Calcula el cambio de cada mes entre 1995–2014 y
2041–2060 (4 modelos, `ssp245` y `ssp585`) y se suma al clima observado (método delta).
Destino: `area_scenario_climate` (`scenario_id = 'ssp245_2050' | 'ssp585_2050'`, `method = 'delta'`),
luego `disease_risk_scenario`, `crop_suitability` futura y `zone_classification`.
Alternativa sin Earth Engine: la API de proyecciones de Open-Meteo (modelos CMIP6 HighResMIP, solo SSP5-8.5;
no es de la NASA, citar como fuente externa).

---

## 8. Provincias de la Sierra con cacao

Bolívar, Cañar, Pichincha y Cotopaxi tienen entre 3 800 y 11 000 ha de cacao (ESPAC 2025).

1. En `tools/fetch_weather.py`, añadir las provincias a `PROVINCES` con región `sierra`.
2. En `crop_phenology`, agregar filas para `region = 'sierra'` (mismos meses de riesgo u otros que indique el experto):
   ```sql
   insert into public.crop_phenology (crop_id, region, stage, months, is_risk_window, source_ref)
   values ('cacao', 'sierra', 'desarrollo_mazorca', '{1,2,3,4,5,6}', true, 'por validar');
   ```
3. Descargar clima y regenerar. Ojo: el cacao de la Sierra crece en valles bajos (menos de 900 m);
   conviene filtrar cantones por altitud (`area_static_features.elevation_mean_m`).

---

## 9. Entrenar el modelo real

Requisito: los puntos 1 y 2 (producción real 2014–2025 y clima completo). Con eso
`v_training_area_year` tendrá ~144 filas con rendimiento **real**. Luego seguir
[05-modelo-predictivo.md](05-modelo-predictivo.md) (`ml/train.py`) y guardar en `model_versions`,
`training_samples` y `loss_predictions`. Para quitar el modelo demo y los datos sintéticos:

```bash
python supabase/seed/inject.py --reset-only      # borra TODO el seed (incluida la producción sintética)
```
y volver a generar **sin producción sintética**:
```bash
python supabase/seed/tools/build_seed.py supabase/seed/raw supabase/seed/data --no-synthetic
python supabase/seed/inject.py --reset --yes
```
(Las hectáreas por cantón y el modelo demo seguirán marcados como sintéticos/demo hasta que haya datos y modelo reales.)
