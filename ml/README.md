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
| `train.py` | 4 | Ridge + GBR cuantílico + ensamble, leave-one-year-out |
| `predict.py` | 5 | Escenarios normal / Niño / actual → API |
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
- **Target**: `y_anom_pct = 100·(R − T)/T`, con T = tendencia LOWESS sin el propio año.
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
