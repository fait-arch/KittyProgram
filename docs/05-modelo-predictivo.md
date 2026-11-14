# 5. Modelo predictivo

**Responde:** *¿cuánta producción de cacao se pierde en cada zona por enfermedades asociadas a
El Niño?* → predice la **caída de rendimiento (%)** a partir del clima y de El Niño, y la
convierte en toneladas y USD.

## 1. Qué predecimos (target)

ESPAC reporta producción y superficie cosechada por provincia y año, de donde sale el
rendimiento (t/ha). El rendimiento sube con los años por tecnología (más CCN-51, mejor manejo),
así que primero se quita esa **tendencia**:

```
anomalía_rendimiento_% = (rendimiento_año − tendencia_año) / tendencia_año × 100
pérdida_%              = max(0, −anomalía_rendimiento_%)
```

- `tendencia` = regresión lineal (o LOWESS) del rendimiento contra el año, **por provincia**,
  ajustada **sin** el año que se evalúa (evita fuga de información).
- Un año Niño con anomalía −20 % → pérdida del 20 % respecto a lo esperado.

> ¿Por qué no "superficie perdida"? ESPAC la reporta mejor para cultivos transitorios; para
> cacao (perenne) la señal más confiable es la caída de rendimiento. Si `lost_ha` existe para
> cacao, se usa como target secundario.

## 2. Unidad de análisis y tamaño

| Nivel | Fuente | Años | Filas aprox. |
|-------|--------|------|--------------|
| **Provincia × año** (principal) | ESPAC | ~2002–2024 | 7 provincias cacaoteras × ~20 años ≈ **140** |
| País × año (apoyo) | FAOSTAT | 1961–2023 | ~60 |

Es un dataset **pequeño** → se prefieren modelos **simples, regularizados y explicables**.
Más datos no se inventan: se compensa con validación honesta e intervalos de incertidumbre.

## 3. Variables de entrada (features)

Calculadas por el ETL para cada área y año, sobre **enero–junio** (época lluviosa de la Costa).
Vienen de la vista `v_training_area_year`.

| Feature | Fuente | Hipótesis |
|---------|--------|-----------|
| `fav_days_monilia` | ERA5-Land | Más días húmedos y templados → más moniliasis |
| `fav_days_phytophthora` | ERA5-Land + GPM | Más días con lluvia y saturación de aire → más mazorca negra |
| `heavy_rain_days` | GPM | Lluvia > 50 mm → caída de flores, inundación |
| `saturated_days` | SMAP (2015→) / GLDAS (antes) | Asfixia radicular |
| `risk_index_mean` | Calculado | Resumen del riesgo |
| `nino12_anom_jan_jun` | NOAA | Intensidad de El Niño frente a Ecuador |
| `oni_jan_jun` | NOAA | El Niño en el Pacífico central |
| `suitability_now` | ECOCROP | Zonas marginales sufren más (vulnerabilidad) |
| `rain_total_vs_opt` | GPM + ECOCROP | Exceso de lluvia sobre el óptimo (3 000 mm) |
| `yield_anom_prev` | ESPAC | Arrastre del año anterior (perenne) |

## 4. Modelos (de simple a más complejo)

| # | Modelo | Para qué |
|---|--------|----------|
| 0 | **Línea base**: pérdida media histórica de años Niño vs no-Niño | Lo mínimo que hay que superar |
| 1 | **Ridge** (regresión lineal regularizada) | Modelo principal: estable con pocos datos, coeficientes interpretables |
| 2 | **Gradient Boosting cuantílico** (p10, p50, p90) | Relaciones no lineales + **intervalo de incertidumbre** |
| 3 | Promedio de 1 y 2 | Si mejora en validación |

Se elige el modelo con menor **MAE** en validación cruzada y que **supere a la línea base**.

## 5. Validación (lo que pide el reto: explicar la incertidumbre)

- **Leave-one-year-out:** se entrena sin un año completo (todas las provincias) y se predice ese
  año. Simula "predecir una temporada que el modelo nunca vio".
- Métricas:
  - **MAE** en puntos de pérdida.
  - **Skill vs línea base** = 1 − MAE_modelo / MAE_base (> 0 = aporta).
  - **Acierto en años Niño**: ¿detecta pérdidas > 10 % en 1998, 2016, 2023–24?
  - **Cobertura del intervalo** p10–p90 (debería contener ≈ 80 % de los casos).
- Se guarda todo en `model_versions.metrics` y la predicción fuera de muestra en
  `training_samples.prediction_cv`.

## 6. De pérdida % a toneladas y USD

```
loss_t   = exposed_ha (crop_exposure) × rendimiento_tendencia (t/ha) × loss_pct / 100
loss_usd = loss_t × precio_promedio (crop_prices, últimos 12 meses)
```

Para **cantones**: el modelo se entrena por provincia, pero se aplica con las features
calculadas **para cada cantón** (mismas definiciones). Se documenta como limitación.

## 7. Escenarios

| Escenario | Features que se usan |
|-----------|---------------------|
| `normal` | Promedio de features en años neutros |
| `nino` | Promedio de features en años Niño |
| `actual` | Features con el ENSO vigente (ONI y Niño 1+2 actuales) + clima normal del área |
| `ssp245_2050`, `ssp585_2050` (F2) | Features recalculadas con el clima delta de CMIP6 |

> Fase 2: el modelo se aplica fuera del rango de clima con el que se entrenó → se muestra con
> advertencia y el rango entre modelos climáticos como incertidumbre adicional.

## 8. Explicabilidad

- Ridge: contribución = coeficiente × (valor − media) → "este factor sumó X puntos de pérdida".
- Gradient Boosting: valores SHAP.
- Se guardan los 3 principales en `loss_predictions.top_factors` y se muestran en el front.

## 9. Código de entrenamiento (`ml/train.py`, esqueleto)

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["fav_days_monilia", "fav_days_phytophthora", "heavy_rain_days",
            "risk_index_mean", "nino12_anom_jan_jun", "oni_jan_jun", "suitability_now"]

def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """Anomalía de rendimiento (%) contra la tendencia de la provincia, sin usar el propio año."""
    out = []
    for area, g in df.groupby("area_id"):
        g = g.sort_values("year").copy()
        trend = []
        for y in g["year"]:
            rest = g[g["year"] != y]
            slope, inter = np.polyfit(rest["year"], rest["yield_t_ha"], 1)
            trend.append(slope * y + inter)
        g["yield_trend"] = trend
        g["yield_anom_pct"] = (g["yield_t_ha"] - g["yield_trend"]) / g["yield_trend"] * 100
        out.append(g)
    return pd.concat(out)

def leave_one_year_out(df, make_model):
    preds = pd.Series(index=df.index, dtype=float)
    for y in sorted(df["year"].unique()):
        train, test = df[df["year"] != y], df[df["year"] == y]
        model = make_model().fit(train[FEATURES], train["yield_anom_pct"])
        preds[test.index] = model.predict(test[FEATURES])
    return preds

def baseline(df):
    preds = pd.Series(index=df.index, dtype=float)
    for y in sorted(df["year"].unique()):
        train, test = df[df["year"] != y], df[df["year"] == y]
        is_nino = train["oni_jan_jun"] >= 0.5
        for i, row in test.iterrows():
            same = train[is_nino] if row["oni_jan_jun"] >= 0.5 else train[~is_nino]
            preds[i] = same["yield_anom_pct"].mean()
    return preds

def train(df: pd.DataFrame) -> dict:
    df = add_target(df.dropna(subset=FEATURES + ["yield_t_ha"])).reset_index(drop=True)
    y = df["yield_anom_pct"]

    ridge = lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30)))
    gbr   = lambda: GradientBoostingRegressor(loss="quantile", alpha=0.5, max_depth=2,
                                              n_estimators=200, learning_rate=0.05, subsample=0.8)

    p_base, p_ridge, p_gbr = baseline(df), leave_one_year_out(df, ridge), leave_one_year_out(df, gbr)
    mae = {k: mean_absolute_error(y, p) for k, p in
           {"base": p_base, "ridge": p_ridge, "gbr": p_gbr}.items()}
    best = min(("ridge", "gbr"), key=mae.get)
    metrics = {"mae": mae, "skill_vs_baseline": 1 - mae[best] / mae["base"], "best": best}

    final = (ridge if best == "ridge" else gbr)().fit(df[FEATURES], y)
    low  = GradientBoostingRegressor(loss="quantile", alpha=0.1, max_depth=2, n_estimators=200,
                                     learning_rate=0.05).fit(df[FEATURES], y)
    high = GradientBoostingRegressor(loss="quantile", alpha=0.9, max_depth=2, n_estimators=200,
                                     learning_rate=0.05).fit(df[FEATURES], y)
    return {"model": final, "low": low, "high": high, "metrics": metrics, "data": df,
            "cv_pred": p_ridge if best == "ridge" else p_gbr}
```

Predicción (`ml/predict.py`, idea):

```python
anom      = model.predict(X_scenario)                 # % (negativo = pérdida)
loss_pct  = np.clip(-anom, 0, 100)
loss_low  = np.clip(-high.predict(X_scenario), 0, 100)   # cuantil alto de anomalía = pérdida baja
loss_high = np.clip(-low.predict(X_scenario), 0, 100)
```

Luego `loss_t`, `loss_usd`, `risk_class` (bajo < 5 %, medio 5–15 %, alto 15–30 %, muy alto
> 30 %) y `top_factors` → `loss_predictions`.

## 10. Estrategias (`ml/strategies.py`)

```
pérdida_con_estrategia = loss_pct × (1 − reducción_estrategia)
pérdida_evitada_usd    = (loss_pct − pérdida_con_estrategia) / 100 × exposed_ha × rend × precio
beneficio_neto         = pérdida_evitada_usd − costo_usd_ha × exposed_ha
```

La **reducción** y el **costo** de cada estrategia vienen de `adaptation_strategies`
(llenar con literatura/INIAP; mientras no haya fuente, se muestra un rango y la marca "por
validar"). Se ordenan por beneficio neto **ponderado por los patógenos que dominan** el riesgo
del cantón (p. ej., si domina la mazorca negra, sube *drenaje + sombra*).

## 11. Limitaciones (se muestran en la app)

1. Pocas observaciones (≈ 140) → intervalos amplios.
2. El rendimiento cae por muchas causas (precio, manejo, plagas no climáticas); el modelo solo
   capta la parte asociada al clima.
3. Umbrales de enfermedad referenciales, no calibrados en campo.
4. Escala provincial para entrenar, cantonal para mostrar.
5. Fase 2 extrapola fuera del clima observado.
