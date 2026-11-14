# Modelo de pérdida (lo entrega ML)

Copiar aquí el bundle entrenado como **`cacao_loss.joblib`** (o cambiar `MODEL_PATH` en `.env`)
y recargar sin reiniciar:

```bash
curl -X POST http://localhost:8000/api/v1/admin/model/reload -H "X-Admin-Key: $ADMIN_API_KEY"
curl http://localhost:8000/health      # model.loaded = true
```

Formato del bundle (un `dict`), detalle en [docs/backend/03-integracion-ml.md](../../docs/backend/03-integracion-ml.md):

```python
{
  "version": "cacao_loss_v1",
  "features": [...],            # orden de columnas
  "model": estimador,           # predice anomalía de rendimiento % (negativo = pérdida)
  "low": q10, "high": q90,      # opcionales: cuantiles de anomalía
  "feature_means": {...},       # para contribuciones y faltantes
  "feature_ranges": {...},      # [min, max] del entrenamiento → aviso fuera de rango
  "scenario_features": {area_id: {scenario_id: {feature: valor}}},  # recomendado
}
```

Los `.joblib` no se versionan (`.gitignore`). ⚠ `joblib.load` ejecuta código: cargar solo
archivos del equipo.
