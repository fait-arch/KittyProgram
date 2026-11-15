# ml/ — Modelo predictivo CacaoResiliente

Predice la **pérdida de rendimiento de cacao (%)** por área y año a partir de datos NASA
(ERA5-Land, GPM, GLDAS/SMAP) y El Niño (NOAA), y la convierte en t y USD.
Diseño completo en [`docs/05-modelo-predictivo.md`](../docs/05-modelo-predictivo.md).

## Setup (Python 3.12)

```bash
uv venv --python 3.12 ml/.venv
uv pip install --python ml/.venv/bin/python -r ml/requirements.txt
ml/.venv/bin/earthengine authenticate      # una vez por máquina
# BACK/.env debe tener GEE_PROJECT=proyectito-uwu-514715
```

## Estructura

| Ruta | Fase | Qué es |
|------|------|--------|
| `config.py` | 0 | Rutas, provincias, años, parámetros ECOCROP |
| `etl/` | 1 | Descarga: ENSO (NOAA), clima GEE, producción FAOSTAT/ESPAC |
| `features.py`, `dataset.py` | 2 | Fórmulas de features y panel área × año |
| `synthetic.py`, `tests/` | 3 | Datos falsos con verdad conocida + tests |
| `model.py`, `train.py` | 4 | Ridge con signos físicos + GBR cuantílico + ensamble, validación leave-one-year-out |
| `scenarios.py`, `inference.py`, `predict.py` | 5 | Escenarios, interfaz para el backend y predicciones por lote |
| `artifacts/` | 4 | `cacao_loss_vX.joblib`, `.onnx`, `model_card_vX.json` |
| `data/raw`, `data/processed` | 1–2 | Datos crudos y Parquet procesado (no versionados) |

## Fase 2 — features y panel

```bash
ml/.venv/bin/python -m ml.etl.worldclim   # climatología de referencia + lat/altitud por área
ml/.venv/bin/python -m ml.etl.exports     # exportaciones FAOSTAT (equivalente de grano)
ml/.venv/bin/python -m ml.dataset         # → data/processed/training_panel.parquet (+ .csv)
ml/.venv/bin/python -m pytest ml/tests
```

- **Corrección de sesgo** (`features.BiasCorrection`, guardada en `artifacts/bias_correction.joblib`):
  temperatura ERA5-Land + delta mensual WorldClim (1961–1990); lluvia ERA5-Land → GPM con
  *quantile mapping* por área y mes. Resultado: una serie homogénea 1961–2025.
- **Features** (ene–jun de cada año): lluvia total / anomalía / extremos, días favorables a
  moniliasis y mazorca negra, suelo saturado, HR, temperatura, ET0 FAO-56, balance hídrico,
  aptitud ECOCROP, lluvia oct–dic previa, ENSO (ONI, Niño 1+2, Niño 3.4).
- **Target**: `y_anom_pct = 100·(R − T)/T`, con T = tendencia LOWESS sin el propio año; R = producción (nacional) o rendimiento (provincias), ver Fase 4.
- **Panel**: 216 filas (nacional 1961–2025 + 7 provincias 2002–2025).

## Fase 3 — datos sintéticos y validación

```bash
ml/.venv/bin/python -m ml.synthetic          # panel con verdad conocida → data/processed/synthetic_panel.parquet
ml/.venv/bin/python -m pytest ml/tests       # 23 tests (~3 min)
```

- `synthetic.py`: `y = Σβ·z(x) − γ·max(0, lluvia − 60 %) + α_area + ruido AR(1)` sobre una tendencia
  tecnológica con el salto de CCN-51; features remuestreadas por año desde el panel real.
  `Truth.linear()`, `Truth()` (no lineal), `Truth.null()` (sin señal) y `stress_scenarios()`.
- `validation.py`: leave-one-year-out que **recalcula el target sin el año de test**, línea base
  (media en años de lluvia extrema / no extrema) y métricas (MAE, skill, cobertura p10–p90,
  acierto en pérdidas > 10 %).
- `dataset.area_anomalies()`: las features se usan como anomalía dentro de cada área (el nivel
  medio lo absorbe la tendencia).

| Verdad | Modelo | Skill vs base | Correlación | Cobertura p10–p90 | Acierto pérdidas grandes |
|--------|--------|---------------|-------------|-------------------|--------------------------|
| Lineal | Ridge | 0.36 | 0.79 | — | 0.77 |
| Lineal | GBR | 0.34 | 0.77 | 0.75 | 0.81 |
| No lineal | Ridge | 0.22 | 0.90 | — | 0.88 |
| No lineal | GBR | 0.28 | 0.92 | 0.73 | 0.82 |
| **Nula** | Ridge / GBR | **0.01 / 0.00** | 0.01 / 0.03 | 0.74 | 0 |

## Fase 4 — modelo, validación y artefactos

```bash
ml/.venv/bin/python -m ml.train --perm 200   # compara modelos, valida y guarda artefactos (~6 min)
ml/.venv/bin/python -m pytest ml/tests       # 40 tests (~5 min)
```

**Modelo final (v1)** — `ml/model.py`, Ridge con signos físicos:

```
z_k   = (x_k − μ_a,k) / σ_a,k                    anomalía del área a (normal climática 1991–2020)
ŷ     = b0 + β_sat·z(suelo saturado) + β_fav·z(días favorables a mazorca negra)
           + β_sol·z(radiación solar) + β_llu·z(lluvia) + β_ext·max(0, z(lluvia) − 2)
           + β_evi·z(verdor MODIS EVI ene–jun)            (sin dato antes de 2000 → z = 0)
        signos fijados por la física (humedad y lluvia ↓, sol y verdor ↑), penalización Ridge (λ por GCV),
        cada término recortado al rango de entrenamiento (no extrapola)
pérdida % = min(100, max(0, −ŷ))        [p10, p90] = ŷ + s_a·[q10, q90]_nivel   (conformal)
```

- **Target**: anomalía % respecto a la tendencia (LOWESS sin el propio año). Nacional: media
  geométrica de **producción** (FAOSTAT 1961–2025) y **exportaciones** en equivalente de grano
  (FAOSTAT comercio 1961–2024), dos medidas independientes de la cosecha. Provincias:
  **producción por hectárea sembrada** (ESPAC 2002–2025): incluye el área que se pierde en los años
  húmedos, que con la hectárea cosechada no se veía.
- Se compararon líneas base, Ridge, GBR cuantílico y su ensamble (peso anidado): el ensamble no
  mejora al Ridge y el GBR no es monótono con pérdida cuantílica → **modelo final = Ridge**.
- **Validación leave-one-year-out** (el año de test sale del entrenamiento, de la tendencia del
  target y de la normal climática):

| Serie nacional (n = 65) | MAE | RMSE | Correlación | R² fuera de muestra |
|---|---|---|---|---|
| "Año normal" (sin clima) | 12,6 | 18,1 | — | 0,00 |
| Niño sí/no según ONI | 12,6 | 17,9 | 0,22 | 0,02 |
| Escalón "lluvia > +100 %" | 11,3 | 15,2 | 0,54 | 0,30 |
| GBR cuantílico | 11,4 | 15,2 | 0,55 | 0,30 |
| **Ridge (modelo final)** | **10,1** | **13,8** | **0,65** | **0,42** |
| Ridge, evaluado contra la producción sola | 11,8 | 14,7 | 0,58 | 0,34 |
| Ridge en **provincias** (n = 137, vs "año normal") | 17,7 vs 18,4 | 22,7 vs 23,6 | **0,28** | **0,07** |

- **Lo que demuestra**: anticipa los Niños extremos sin haberlos visto (1983 → −48 %, real −50 %;
  1998 → −38 %, real −64 %). Test de permutación p = 0,005. Bloques de 3 años: corr 0,67.
- **Provincias**: skill pequeño pero **significativo**: corr 0,28, R² 0,07, test de permutación
  provincial **p = 0,01** (al empezar: 0,10 y 0,00). Viene del verdor de MODIS y del target por hectárea
  sembrada. Bloques de 3 años: 0,22.
- **Lo que no** (auditoría independiente, también en la model card):
  - Depende sobre todo de la **lluvia extrema**: sin 1983/1998 la correlación baja a 0,44 (el MAE sí
    mejora a "año normal": 10,0 vs 11,2). Entrenando sin ambos, cada uno se predice en solo −18 %.
  - En **provincias el skill es pequeño** (R² 0,07; ruido ESPAC 15–31 %): explica poco de cada año.
    La salida por zona sigue llevando `evidence = "indice_subnacional_no_validado"`.
  - El verdor (EVI) se **observa**: sirve para la temporada en curso (desde julio) pero no existe para
    2050 ni para 1983/1998; ahí entra como "verdor normal".
  - El índice Niño 1+2 no aporta una vez conocida la lluvia: hace falta el clima de ene–jun.
  - El intervalo cubre 78 % (nacional) / 74 % (provincias), pero casi no es más estrecho que el de
    "año normal": transmite sobre todo la incertidumbre.
  - Eligiendo las decisiones de diseño dentro de cada pliegue, la correlación honesta es 0,50–0,56.

**Artefactos** (`ml/artifacts/`):

| Archivo | Qué es |
|---|---|
| `cacao_loss_v1.joblib` | Bundle para el backend (versionado, 20 KB; se regenera con `ml.train`) |
| `model_card_v1.json` | Fórmula con todos sus números (reproducible sin Python), métricas, límites |
| `cv_predictions_v1.csv` | Predicción fuera de muestra, p10 y p90 de cada área-año |

```python
import joblib
model = joblib.load("ml/artifacts/cacao_loss_v1.joblib")
model.predict(df)   # df: area_name, year, saturated_days, fav_days_phytophthora, solar_mean, rain_total
# → y_anom_pct, y_anom_p10/p90, loss_pct, loss_p10/p90, risk_class, top_factors,
#   extrapolated, evidence, model_version
model.model.pre_.add_area("Vinces", historial_features)   # cantón nuevo: necesita ≥10 años 1991–2020
```

## Fase 5 — entrega para el backend y predicciones por escenario

El backend, Supabase y el front son del resto del equipo; aquí solo se entrega lo que necesitan
para enchufar el modelo, según el contrato de `docs/backend/03-integracion-ml.md` (rama
`emilio/backend`).

```bash
ml/.venv/bin/python -m ml.train     # → artifacts/cacao_loss_v1.joblib (bundle para el backend)
ml/.venv/bin/python -m ml.predict   # → artifacts/loss_predictions_v1.csv/.parquet + model_version_v1.json
```

**Para el backend (modo en vivo / what-if)** — en `BACK/.env`:

```
MODEL_PATH=../ml/artifacts/cacao_loss_v1.joblib
ML_INFERENCE_MODULE=ml.inference
```

- El bundle es un `dict` con `version`, `features`, `model`, `feature_ranges`, `feature_means`,
  `explain`, `sklearn_version`, `scenario_features`, `sensitivities`, `scenario_years`, `metrics`.
- `ml/inference.py` expone las dos funciones del contrato:
  - `adjust_features(features, adjust, area_ctx)`: sliders `rain_delta_pct`, `temp_delta_c`,
    `nino12_anom`, `oni`. La lluvia arrastra al suelo saturado, a los días favorables y a la
    radiación con las pendientes históricas de cada área; El Niño cambia la lluvia esperada.
  - `predict(bundle, features)` → `loss_pct`, `loss_pct_low`, `loss_pct_high`,
    `top_factors` (`feature`, `value`, `contribution_pct` > 0 = suma pérdida), `out_of_range`,
    `risk_class`, `evidence`.
- **Áreas por nombre** (`national`, `Los Rios`, …). Con uuid de Supabase:
  `attach_area_ids(bundle, {uuid: nombre})`. Cantón nuevo: `register_area(bundle, id, historial)`
  (≥ 10 años de features 1991–2020). El vector lleva `_area` (o `_province`) para elegir la normal.
- Misma versión de scikit-learn en `BACK/requirements.txt` que en `ml/` (1.9.1).

**Para Supabase (modo lote)** — `loss_predictions_v1.csv` tiene las columnas de la tabla
`loss_predictions` (por nombre de área; falta mapear a `area_id`) y `model_version_v1.json` la fila
de `model_versions`.

**Escenarios** (`ml/scenarios.py`, mismos ids que la tabla `scenarios`):

| id | Años | Pérdida nacional esperada |
|---|---|---|
| `normal` | ENSO neutros 2001–2025 | 2 % |
| `nino` | El Niño (ONI) 2001–2025 | 0 % |
| `nina` | La Niña 2001–2025 | 2 % |
| `nino_extremo` | 1983, 1998 | 54 % |
| `actual` | análogos: Niño 1+2 ago–oct previo ≥ +2 °C → 1998, 2016, 2024 | 20 % |

- La pérdida de un escenario es la **media de las pérdidas de sus años** (un año promedio no
  existe y diluye los extremos).
- El "Niño" según el ONI casi no da pérdidas: en 2001–2025 esos años no fueron lluviosos en la
  costa. Lo que daña es el **Niño costero con lluvia extrema** (`nino_extremo`).
- `actual`: hoy (oct 2026) Niño 1+2 está en +5,3 °C, más que en 1997. De los 3 análogos, uno fue
  extremo (1998) y dos no (2016, 2024): por eso 20 % con un rango amplio. Se actualiza solo al
  re-ejecutar con los datos ENSO nuevos.
- Toneladas y USD: hectáreas y rendimiento de tendencia del último año, precio FAOSTAT del último
  año disponible (2024: 5 602 USD/t, año de precio récord).

### Intentos de mejora que NO se adoptaron (validados igual: leave-one-year-out y bloques de 3 años)

| Intento | Correlación nacional | RMSE | Por qué no |
|---|---|---|---|
| Modelo anterior (target = solo producción) | 0,54 | 15,3 | — |
| + lluvia extrema 1–2 años antes (efecto post-Niño) | 0,45–0,55 | 15,5–16,4 | Las caídas de 2000–2002 coinciden con la crisis de la dolarización y un salto de la superficie FAOSTAT, no con el clima |
| Lluvia ERA5 calibrada con CHIRPS (en vez de GPM) | 0,54 | 15,3 | Igual: no aporta |
| Lluvia observada CHIRPS 1981→ | 0,45 | 16,3 | CHIRPS suaviza los extremos (1998: +93 % vs +126 % de GPM) |

| Ventanas de meses (ene–abr, feb–may, mar–jun…) y lluvia oct–dic previa | 0,37–0,55 | 15,3–16,8 | Ninguna supera a ene–jun |
| Producción o área como target provincial | prov 0,07–0,13 | — | Sin skill provincial igual |
| **Target nacional = producción + exportaciones (ADOPTADO)** | **0,64** (0,56 vs producción sola) | **14,1** | Dos medidas independientes de la cosecha: menos ruido |
| **Target provincial = producción por ha SEMBRADA (ADOPTADO)** | nacional 0,65; prov 0,20 → **0,28** (p = 0,01) | 13,8 | Cuenta el área perdida por enfermedad o inundación (la fracción cosechada baja con la lluvia: r = −0,2) |
| Verdor solo en píxeles de cultivo (ESA WorldCover), NDVI, otros meses, temporada previa (26 variantes) | 0,61–0,65; prov 0,10–0,22 | 13,8–14,5 | Ninguna mejora a la vez nacional y provincias; elegir la mejor sería inflar |
| + 4 provincias andinas (Bolívar, Cotopaxi, Pichincha, Cañar), +96 filas | 0,66; prov 0,20 → 0,18 | — | Su ESPAC es aún más ruidoso (±46–75 %). Su clima se usa solo para el índice por zona |
| **+ verdor MODIS EVI ene–jun (ADOPTADO)** | **0,65**; provincias 0,10 → **0,20** | **13,8** | Medida satelital del estado del cultivo, independiente de la encuesta (recurso del reto) |

CHIRPS queda en el ETL (`--datasets chirps`) y en `BiasCorrection.fit(rain_ref=…, use_obs=…)` por si
se quiere revisar. El límite de precisión está en los datos de producción (solo dos Niños extremos y
estadísticas provinciales ruidosas), no en el modelo.
