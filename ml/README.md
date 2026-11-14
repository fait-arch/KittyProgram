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
        signos fijados por la física (humedad y lluvia ↓, sol ↑), penalización Ridge (λ por GCV),
        cada término recortado al rango de entrenamiento (no extrapola)
pérdida % = min(100, max(0, −ŷ))        [p10, p90] = ŷ + s_a·[q10, q90]_nivel   (conformal)
```

- **Target**: anomalía % respecto a la tendencia (LOWESS sin el propio año) de la **producción**
  (nacional, FAOSTAT 1961–2025) o del **rendimiento** (provincias, ESPAC 2002–2025).
- Se compararon líneas base, Ridge, GBR cuantílico y su ensamble (peso anidado): el ensamble no
  mejora al Ridge y el GBR no es monótono con pérdida cuantílica → **modelo final = Ridge**.
- **Validación leave-one-year-out** (el año de test sale del entrenamiento, de la tendencia del
  target y de la normal climática):

| Serie nacional (n = 65) | MAE | RMSE | Correlación | R² fuera de muestra |
|---|---|---|---|---|
| "Año normal" (sin clima) | 12,8 | 18,1 | — | 0,00 |
| Niño sí/no según ONI | 13,0 | 18,2 | 0,01 | −0,01 |
| Escalón "lluvia > +100 %" | 11,6 | 15,7 | 0,50 | 0,25 |
| GBR cuantílico | 12,7 | 16,3 | 0,45 | 0,19 |
| **Ridge (modelo final)** | **12,0** | **15,3** | **0,54** | **0,29** |

- **Lo que demuestra**: anticipa los Niños extremos sin haberlos visto (1983 → −46 %, real −46 %;
  1998 → −30 %, real −59 %). Test de permutación p = 0,005. Bloques de 3 años: corr 0,55.
- **Lo que no** (auditoría independiente, también en la model card):
  - Es un **detector de lluvia extrema**: sin 1983/1998 la correlación cae a 0,30 y el MAE no mejora
    a "año normal". Entrenando sin ambos, cada uno se predice en solo −11 / −13 %.
  - En **provincias no hay skill** (ruido ESPAC 15–31 %): la salida por zona lleva
    `evidence = "indice_subnacional_no_validado"`.
  - El índice Niño 1+2 no aporta una vez conocida la lluvia: hace falta el clima de ene–jun.
  - El intervalo cubre 78 % (nacional) / 73 % (provincias), pero casi no es más estrecho que el de
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
| `nino_extremo` | 1983, 1998 | 48 % (27–68) |
| `actual` | análogos: Niño 1+2 ago–oct previo ≥ +2 °C → 1998, 2016, 2024 | 18 % (11–37) |

- La pérdida de un escenario es la **media de las pérdidas de sus años** (un año promedio no
  existe y diluye los extremos).
- El "Niño" según el ONI casi no da pérdidas: en 2001–2025 esos años no fueron lluviosos en la
  costa. Lo que daña es el **Niño costero con lluvia extrema** (`nino_extremo`).
- `actual`: hoy (oct 2026) Niño 1+2 está en +5,3 °C, más que en 1997. De los 3 análogos, uno fue
  extremo (1998) y dos no (2016, 2024): por eso 18 % con un rango amplio. Se actualiza solo al
  re-ejecutar con los datos ENSO nuevos.
- Toneladas y USD: hectáreas y rendimiento de tendencia del último año, precio FAOSTAT del último
  año disponible (2024: 5 602 USD/t, año de precio récord).
