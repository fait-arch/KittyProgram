# 3. Integración con el modelo de ML

Base: [docs/05-modelo-predictivo.md](../05-modelo-predictivo.md). Aquí está el **contrato** entre
el modelo y el backend, para que cada uno trabaje sin bloquear al otro.

## 1. Dos modos de integración (ambos soportados)

| Modo | Cómo | Cuándo |
|------|------|--------|
| **A. Batch (principal)** | ML corre `predict.py` y escribe `loss_predictions` + `strategy_evaluations`. El backend solo lee. | Siempre. Es lo que pinta el mapa. |
| **B. En vivo (what-if)** | El backend carga el artefacto del modelo activo y predice al vuelo en `POST /predict`. | Sliders de lluvia/temperatura/Niño. |

Variable `PREDICTOR_MODE` en `.env`:

| Valor | Efecto |
|-------|--------|
| `local` | El backend importa el paquete `ml` y carga el `.joblib` (defecto) |
| `remote` | El backend reenvía a `ML_SERVICE_URL/predict` (si ML prefiere su propio servicio) |
| `off` | `/predict` responde `503`; el resto funciona |

## 2. Contrato del modo batch (tablas)

### `model_versions`

- Exactamente **una** fila `is_active = true` por `crop_id` (índice único ya existe).
- `features`: lista **ordenada** de nombres (los de la tabla § 3).
- `metrics` (jsonb), con estas claves mínimas, que el backend muestra en `/meta`:

```json
{ "mae": 6.3, "mae_baseline": 8.0, "skill_vs_baseline": 0.21,
  "interval_coverage_p10_p90": 0.78, "nino_years_hit": {"1998": true, "2016": true, "2024": false},
  "best": "ridge" }
```

- `artifact_path`: ruta en Supabase Storage, bucket `models`, p. ej. `cacao/cacao_loss_v1.joblib`.

### `loss_predictions`

Una fila por `(model_version_id, area_id, crop_id, scenario_id)`, con todos los campos llenos.
Para `canton` **y** `province` (el mapa usa los dos niveles).

`top_factors` — formato fijo (ordenado de mayor a menor contribución, máx. 5):

```json
[{ "feature": "fav_days_monilia", "value": 118, "contribution_pct": 9.8 }]
```

`contribution_pct` = puntos de pérdida que suma ese factor (positivo = aumenta la pérdida).
Ridge: `−coef × (x − media)` (signo invertido porque el target es anomalía, la pérdida es −anomalía).

**Vector base del what-if:** como `loss_predictions` no guarda features, incluir en el bundle
`scenario_features = {area_id: {scenario_id: {feature: valor}}}`. Si falta, el backend lo
reconstruye desde `disease_risk_scenario` y `area_scenario_climate` (menos exacto).

`risk_class` según `loss_pct`: `bajo` < 5 · `medio` 5–15 · `alto` 15–30 · `muy_alto` > 30.

### `strategy_evaluations`

Una fila por `(prediction_id, strategy_id)` incluyendo `actual`. `rank` 1 = mejor beneficio neto.
`evidence` = `[{variable_id, source_id, statement}]`. `why`, `data_gaps`, `risks` en español
llano. *(Quién escribe esta tabla: decisión abierta D2 en [05](05-pendientes.md).)*

### Al terminar `predict.py`

```bash
curl -X POST "$BACKEND_URL/api/v1/admin/cache/clear" -H "X-Admin-Key: $ADMIN_API_KEY"
```

## 3. Diccionario de features (nombres = contrato)

El backend usa esta tabla para las etiquetas que ve el agricultor. **Si ML agrega o renombra
una feature, se agrega aquí** (y en `BACK/app/schemas/features.py`).

| `feature` | Etiqueta para el agricultor | Unidad |
|-----------|-----------------------------|--------|
| `fav_days_monilia` | Días muy húmedos que favorecen la moniliasis (ene–jun) | días |
| `fav_days_phytophthora` | Días de lluvia y humedad que favorecen la mazorca negra (ene–jun) | días |
| `heavy_rain_days` | Días de aguacero (> 50 mm) | días |
| `saturated_days` | Días con el suelo encharcado | días |
| `risk_index_mean` | Riesgo climático de enfermedad promedio | 0–1 |
| `nino12_anom_jan_jun` | Calentamiento del mar frente a Ecuador | °C |
| `oni_jan_jun` | Intensidad de El Niño en el Pacífico | °C |
| `suitability_now` | Qué tan apto es el clima para el cacao | 0–1 |
| `rain_total_vs_opt` | Lluvia por encima de lo que el cacao necesita | mm |
| `yield_anom_prev` | Cómo le fue a la cosecha el año anterior | % |

## 4. Contrato del modo en vivo (artefacto)

El `.joblib` es un **diccionario** (no solo el estimador), para que el backend no necesite
conocer el algoritmo:

```python
bundle = {
    "version": "cacao_loss_v1",
    "features": [...],                 # mismo orden que model_versions.features
    "model": final_estimator,          # predice anomalía % (negativo = pérdida)
    "low": gbr_q10, "high": gbr_q90,   # cuantiles de anomalía
    "feature_means": {...},            # para contribuciones y para rellenar faltantes
    "feature_ranges": {"fav_days_monilia": [12, 170], ...},  # min/max del entrenamiento → aviso
    "explain": "linear" | "shap",
    "sklearn_version": "1.5.2",
}
joblib.dump(bundle, "cacao_loss_v1.joblib")
```

Y el paquete `BACK/ml/` expone **dos funciones puras** que el backend importa (ML es dueño de
la lógica, backend solo de HTTP):

```python
# BACK/ml/inference.py   (lo escribe ML; el backend solo lo llama)
def adjust_features(features: dict, adjust: dict, area_ctx: dict) -> dict:
    """Aplica los sliders al vector base.
    adjust = {"temp_delta_c": 1.0, "rain_delta_pct": 25, "nino12_anom": 3.0, "oni": 2.0}
    area_ctx = climatología mensual del área (de area_scenario_climate), por si hace falta.
    Reglas mínimas aceptadas para F1.5:
      · nino12_anom / oni → reemplazan nino12_anom_jan_jun / oni_jan_jun
      · rain_delta_pct    → escala heavy_rain_days, rain_total_vs_opt y fav_days_phytophthora
      · temp_delta_c      → desplaza fav_days_* con la sensibilidad estimada en entrenamiento
    """

def predict(bundle: dict, features: dict) -> dict:
    """→ {"loss_pct", "loss_pct_low", "loss_pct_high", "top_factors": [...], "out_of_range": bool}"""
```

El backend completa `loss_t`, `loss_usd` y `risk_class` con `exposed_ha`,
`expected_yield_t_ha` y `price_usd_t` de la fila base de `loss_predictions`
(misma fórmula que §6 de 05-modelo-predictivo).

**Requisito:** misma versión de `scikit-learn` en `ml/requirements.txt` y `BACK/requirements.txt`
(se fija en ambos; si no, `joblib.load` puede fallar).

### Modo `remote` (si ML levanta su propio servicio)

`POST {ML_SERVICE_URL}/predict` con `{"features": {...}}` → misma respuesta que `predict()`.
El backend sigue siendo quien habla con el front.

## 5. Mientras el modelo no exista

- `USE_MOCKS=true` → `/losses`, `/detail`, `/strategies` devuelven `BACK/app/mocks/*.json`.
- Línea base del propio doc de ML (pérdida media Niño vs no-Niño) puede escribirse en
  `loss_predictions` con `model_versions.algorithm = 'baseline'` para tener datos reales
  mínimos antes del modelo final.

## 6. Checklist para ML

- [ ] `model_versions` con `is_active`, `features`, `metrics` (claves § 2), `artifact_path`
- [ ] `loss_predictions` para `normal`, `nino`, `actual` × cantones y provincias, con `features` y `top_factors`
- [ ] Artefacto `.joblib` (formato § 4) subido al bucket `models`
- [ ] `ml/inference.py` con `adjust_features` y `predict`
- [ ] Llamar `/admin/cache/clear` al terminar
