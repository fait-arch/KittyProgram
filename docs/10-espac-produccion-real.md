# 10. Producción real de cacao por provincia — ESPAC 2002–2025

Fecha: 2026-11-14. Resuelve el punto 2 de [09](09-como-conseguir-los-datos-que-faltan.md):
producción **real** por provincia (antes solo 2023–2025 eran reales; 2001–2022 eran sintéticos).

## ⚠ No hay datos de 2001

La **ESPAC del INEC empieza en 2002**: no existe tabulado de 2001. Consecuencias:

- 2001 **sigue siendo sintético** por provincia en el seed (`source_id = 'seed_sintetico'`).
- Para 2001 solo hay dato **nacional** real: FAOSTAT (76 030 t, 429 547 ha cosechadas), ya cargado.
- Al entrenar el modelo, usar **2002 en adelante** con datos reales, o descartar 2001
  (`where source_id = 'espac'`).

## De dónde salen los datos

**Fuente:** INEC — Encuesta de Superficie y Producción Agropecuaria Continua (ESPAC), tabulados
anuales en Excel. Tabla *"Superficie, producción y ventas, según región y provincia — cacao
(almendra seca)"*: **T13** en 2002–2015, **T14** desde 2016.

Página: https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/ →
*Información de años anteriores ESPAC*. Descarga directa (las mismas URLs que usa
`ml/etl/production.py` de la rama `beltranfuego`), base
`https://www.ecuadorencifras.gob.ec/documentos/web-inec/Estadisticas_agropecuarias/espac`:

| Años | Ruta |
|------|------|
| 2002–2013 | `/Publicaciones-espac/INDICE_PUBLICACION%20ESPAC%20<AÑO>.xlsx` |
| 2014 | `/espac_2014-2015/2014/Indice%20de%20publicacion%20ESPAC-2014.xlsx` |
| 2015 | `/espac_2014-2015/2015/Indice%20de%20publicacion%20ESPAC%202015.xlsx` |
| 2016 | `/espac-2016/Indice%20de%20publicacion%20ESPAC%202016.xlsx` |
| 2017 | `/espac_2017/Indice_de%20publicacion_ESPAC_2017.xlsx` |
| 2018–2021 | `/espac-<AÑO>/Tabulados%20ESPAC%20<AÑO>.xlsx` |
| 2022 | `/espac_2022/Tabulados%20ESPAC%202022.xlsx` |
| 2023 | `/2023/Tabulados_ESPAC_2023.xlsx` |
| 2024 | `/2024/Tabulados_ESPAC_2024.xlsx` |
| 2025 | `/2025/Tabulados_excel_2025.xlsx` |

Los 24 archivos se guardaron como `supabase/seed/raw/espac/espac_tab<AÑO>.xlsx` (no se versionan:
`raw/` está en el `.gitignore`). Descarga con `curl -L -A "Mozilla/5.0" -o espac_tab<AÑO>.xlsx <URL>`.

## Cómo se procesaron

Script: [`supabase/seed/tools/espac_to_sql.py`](../supabase/seed/tools/espac_to_sql.py) (lector basado en
`ml/etl/production.py`).

1. Busca la tabla de cacao por provincia en el índice del libro (o por el título de la hoja).
2. Por cada provincia suma las filas **"Solo" + "Asociado"**: superficie plantada, cosechada,
   producción (t) y ventas (t). `.` = sin dato; `*` = oculto por confidencialidad (se marca).
3. **Control de cuadre:** provincias + agregados no provinciales = total nacional (±2 %).
   Los agregados son:
   - **2002–2011:** la Amazonía se publicaba por subregión (*Nororiente*, *Centro-Suroriente*),
     no por provincia → esas provincias no tienen filas antes de 2012 (no se inventó un reparto).
   - **2014–2018:** *Zonas no delimitadas*.
4. Cruza cada provincia con `public.areas` por **código DPA del INEC** (`inec_dpa_code`).

Resultado del control (los 24 años cuadran):

| Años | Producción nacional (t) | Provincias | Nota |
|------|------------------------:|-----------:|------|
| 2002 | 60 268 | 15 | + 1 893 t Amazonía agregada |
| 2012 | 133 323 | 23 | cuadre exacto |
| 2016 | 177 551 | 23 | + 1 313 t zonas no delimitadas |
| 2025 | 501 244 | 23 | cuadre exacto; 2023–2025 = los valores que ya tenía el seed |

## Qué se carga en Supabase

Archivo: [`supabase/seed/data/07_espac_real.sql`](../supabase/seed/data/07_espac_real.sql) (una transacción):

1. Borra las filas **sintéticas** (`seed_sintetico`) de las provincias × años que ahora tienen dato real.
2. Inserta/actualiza las filas reales en `crop_production_stats` (`source_id = 'espac'`).
3. Inserta/actualiza el total nacional ESPAC en el área `country`.

| Provincia | Años reales |
|-----------|-------------|
| El Oro, Esmeraldas, Guayas, Los Ríos, Manabí | 2002–2025 |
| Santo Domingo de los Tsáchilas | 2009–2025 (provincia creada en 2007) |
| Morona Santiago, Napo, Orellana, Sucumbíos, Zamora Chinchipe | 2012–2025 |
| Pastaza | 2012–2025 (13 años con superficie cosechada) |

**220 filas provinciales + 24 nacionales.** Las provincias de la Sierra (Bolívar, Cotopaxi,
Pichincha, Cañar…) están en el CSV pero **no se cargan** porque no existen en `areas` (ver [08](08-informe-datos.md) § 4.7).

Datos completos (todas las provincias, incluida la Sierra), **versionados**:
[`supabase/seed/data/espac_cacao_provincias.csv`](../supabase/seed/data/espac_cacao_provincias.csv) (478 filas, 54 KB) y
[`espac_cacao_nacional.csv`](../supabase/seed/data/espac_cacao_nacional.csv). Columnas: `year, province, name_key, dpa,
planted_ha, harvested_ha, production_t, sales_t, yield_t_ha, hidden_values, year_ok, sheet`.
Los Excel originales (91 MB) no se versionan: están en `supabase/seed/raw/espac/` y se regeneran con las URLs de arriba.

```python
import pandas as pd
df = pd.read_csv("supabase/seed/data/espac_cacao_provincias.csv")   # para ML, sin pasar por Supabase
```

## Cómo inyectar (no se ha ejecutado todavía)

```bash
# regenerar (si cambian los Excel)
python -I supabase/seed/tools/espac_to_sql.py supabase/seed/raw/espac supabase/seed/data
# cargar solo esta parte (después de las partes 01–06); requiere SUPABASE_DB_URL en BACK/.env
python supabase/seed/inject.py --only 7
```

O pegar `07_espac_real.sql` en el SQL Editor de Supabase. Comprobar:

```sql
select * from public.v_production_provenance where year between 2002 and 2025 order by year;
```
