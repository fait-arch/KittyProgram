"""Validación honesta del modelo: leave-one-year-out (LOYO) sin fuga de información.

Para cada año de test:
  1. La tendencia de rendimiento (y por tanto el target) se recalcula SIN ese año,
     tanto para entrenamiento como para test (`add_target(exclude={año})`).
  2. Se entrena con todos los demás años (todas las áreas) y se predice el año de test.

Así se simula "predecir una temporada que el modelo nunca vio", que es lo que hará la API.

Un modelo es un objeto con `fit(X, y)` y `predict(X)`; si además tiene `predict_quantiles(X)`
que devuelve (p10, p50, p90), se evalúa también la cobertura del intervalo.
"""
from __future__ import annotations

from typing import Callable, Protocol

import numpy as np
import pandas as pd

from .dataset import TARGET, add_target


class Model(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series): ...
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


PROD_COLS = ["area_name", "year", "yield_t_ha"]


def loyo(panel: pd.DataFrame, make_model: Callable[[], Model], features: list[str],
         years: list[int] | None = None, retrend: bool = True) -> pd.DataFrame:
    """Predicciones fuera de muestra. Devuelve panel con columnas pred, y_cv (target sin fuga)
    y, si el modelo lo permite, p10/p90."""
    years = years or sorted(panel.year.unique())
    out = []
    for yr in years:
        if retrend:
            prod = add_target(panel[PROD_COLS], exclude={yr})[["area_name", "year", TARGET, "y_anom_prev"]]
            df = panel.drop(columns=[TARGET, "y_anom_prev"], errors="ignore").merge(prod, on=["area_name", "year"])
        else:
            df = panel
        train = df[(df.year != yr)].dropna(subset=features + [TARGET])
        test = df[df.year == yr].dropna(subset=features + [TARGET])
        if test.empty:
            continue
        m = make_model().fit(train[features], train[TARGET])
        res = test[["area_name", "year", "level", TARGET]].rename(columns={TARGET: "y_cv"}).copy()
        res["pred"] = m.predict(test[features])
        if hasattr(m, "predict_quantiles"):
            lo, _, hi = m.predict_quantiles(test[features])
            res["p10"], res["p90"] = lo, hi
        out.append(res)
    return pd.concat(out, ignore_index=True)


class NinoBaseline:
    """Línea base del plan: anomalía media de los años de entrenamiento con la misma
    condición (lluvia extrema / no extrema). Es lo mínimo que un modelo debe superar."""

    def __init__(self, col: str = "rain_anom_pct", threshold: float = 60.0):
        self.col, self.threshold = col, threshold

    def fit(self, X, y):
        wet = X[self.col] > self.threshold
        self.mean_wet = y[wet].mean() if wet.any() else y.mean()
        self.mean_dry = y[~wet].mean()
        return self

    def predict(self, X):
        return np.where(X[self.col] > self.threshold, self.mean_wet, self.mean_dry)


def metrics(cv: pd.DataFrame, base: pd.DataFrame | None = None, loss_threshold: float = 10.0) -> dict:
    """MAE, skill vs línea base, cobertura p10–p90 y detección de pérdidas grandes."""
    err = (cv.y_cv - cv.pred).abs()
    m = {"n": int(len(cv)), "mae": float(err.mean()), "rmse": float(np.sqrt(((cv.y_cv - cv.pred) ** 2).mean())),
         "corr": float(cv.y_cv.corr(cv.pred))}
    if base is not None:
        b = base.set_index(["area_name", "year"]).pred.reindex(cv.set_index(["area_name", "year"]).index)
        m["mae_base"] = float((cv.y_cv.to_numpy() - b.to_numpy()).__abs__().mean())
        m["skill"] = 1 - m["mae"] / m["mae_base"]
    if {"p10", "p90"} <= set(cv):
        m["coverage_80"] = float(((cv.y_cv >= cv.p10) & (cv.y_cv <= cv.p90)).mean())
        m["interval_width"] = float((cv.p90 - cv.p10).mean())
    big = cv.y_cv < -loss_threshold
    if big.any():
        m["hit_rate_big_loss"] = float((cv.pred[big] < -loss_threshold / 2).mean())
        m["false_alarm"] = float((cv.pred[~big] < -loss_threshold).mean())
    return m
