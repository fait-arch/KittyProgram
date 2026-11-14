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
