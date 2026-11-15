"""Experimento 3 — probabilidad de año malo:  P(pérdida > 20 %)  en vez del % exacto.

Tres formas de dar la probabilidad, todas en leave-one-year-out sin fuga:

    clima    p = frecuencia histórica de años malos en el área (lo mínimo a superar)
    logit    p = σ(b0 + Σ b_k·t_k)  regresión logística L2 con los mismos términos del modelo
             (anomalías z por área + umbral de lluvia extrema), C elegido por CV interna
    ridge    p = P(ŷ + s_a·r < −20)  con el modelo actual: su predicción + la distribución de sus
             errores fuera de muestra (residuos normalizados de años lejanos, como el intervalo)

Métricas: Brier = media (p − o)²  (o = 1 si fue año malo), Brier skill = 1 − Brier/Brier_clima,
AUC (¿ordena bien los años malos sobre los buenos?), y acierto/falsas alarmas con p ≥ 0.5.

    ml/.venv/bin/python -m ml.experiments.probability
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import roc_auc_score

from ml.dataset import OUTPUT, TARGET
from ml.model import CORE, Preprocessor, RidgeModel
from ml.train import CALIB_GAP, KEY, _area_scale, load_data
from ml.validation import fold_targets, loyo

BAD = -20.0
RESULTS = __import__("pathlib").Path(__file__).parent / "results"


class LogitModel:
    """σ(b0 + Σ b·t): mismos términos que el Ridge (Preprocessor de ml.model)."""

    def __init__(self, climate):
        self.climate = climate

    def fit(self, X, y):
        self.pre = Preprocessor(CORE, self.climate).fit(X)
        Z = self.pre.transform(X)
        self.mu, self.sd = Z.mean(), Z.std().replace(0, 1)
        o = (y < BAD).astype(int)
        self.const = None
        if o.nunique() < 2:
            self.const = float(o.mean())
            return self
        self.m = LogisticRegressionCV(Cs=np.logspace(-2, 1, 10), cv=5, scoring="neg_brier_score",
                                      max_iter=2000).fit((Z - self.mu) / self.sd, o)
        return self

    def predict(self, X):                      # loyo llama predict: devolvemos la probabilidad
        if self.const is not None:
            return np.full(len(X), self.const)
        return self.m.predict_proba((self.pre.transform(X) - self.mu) / self.sd)[:, 1]


class Climatology:
    def fit(self, X, y):
        self.p = (y < BAD).groupby(X.area_name.to_numpy()).mean().to_dict()
        self.all = float((y < BAD).mean())
        return self

    def predict(self, X):
        return X.area_name.map(self.p).fillna(self.all).to_numpy(float)


def ridge_probability(cv: pd.DataFrame) -> pd.DataFrame:
    """P(y < BAD) = fracción de los residuos normalizados (años lejanos) que llevarían a < BAD."""
    out = []
    for yr, test in cv.groupby("year"):
        rest = cv[(cv.year - yr).abs() >= CALIB_GAP]
        scale = _area_scale(rest)
        r = ((rest.y_cv - rest.pred) / rest.area_name.map(scale)).to_numpy()
        s = test.area_name.map(scale).to_numpy()
        p = [(pred + si * r < BAD).mean() for pred, si in zip(test.pred, s)]
        out.append(test.assign(prob=p))
    return pd.concat(out, ignore_index=True)


def evaluate(df: pd.DataFrame, prob: str, clim: str = "p_clim") -> dict:
    o = (df.y_cv < BAD).astype(int)
    brier = float(((df[prob] - o) ** 2).mean())
    ref = float(((df[clim] - o) ** 2).mean())
    m = {"n": int(len(df)), "malos": int(o.sum()), "brier": brier, "brier_skill": 1 - brier / ref,
         "auc": float(roc_auc_score(o, df[prob])) if 0 < o.sum() < len(o) else None}
    alert = df[prob] >= 0.5
    m["acierto_p50"] = float(alert[o == 1].mean()) if o.sum() else None
    m["falsa_alarma_p50"] = float(alert[o == 0].mean())
    return m


def run(verbose: bool = True) -> dict:
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    T = fold_targets(panel, value=OUTPUT)
    common = dict(value=OUTPUT, targets=T, allow_nan=CORE.fill_zero)
    clim = loyo(panel, Climatology, CORE.columns, **common).rename(columns={"pred": "p_clim"})
    logit = loyo(panel, partial(LogitModel, climate), CORE.columns, **common).rename(columns={"pred": "p_logit"})
    ridge = ridge_probability(loyo(panel, partial(RidgeModel, CORE, climate), CORE.columns, **common))
    df = clim.merge(logit[KEY + ["p_logit"]], on=KEY).merge(ridge[KEY + ["prob"]].rename(
        columns={"prob": "p_ridge"}), on=KEY)
    res = {}
    for lvl in ("national", "province"):
        d = df[df.level == lvl]
        res[lvl] = {k: evaluate(d, c) for k, c in (("clima", "p_clim"), ("logit", "p_logit"),
                                                    ("ridge", "p_ridge"))}
    if verbose:
        for lvl, r in res.items():
            print(f"\n{lvl}  (año malo = pérdida > {-BAD:.0f} %)")
            print(pd.DataFrame(r).T.round(3).to_string())
        nat = df[df.level == "national"].set_index("year")
        print("\nNacional, probabilidad de año malo (sin haber visto el año):")
        print(nat.loc[[1983, 1987, 1992, 1998, 2000, 2002, 2016, 2023, 2024],
                      ["y_cv", "p_clim", "p_logit", "p_ridge"]].round(2).T.to_string())
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp3_probability.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    df.round(4).to_csv(RESULTS / "exp3_probability_cv.csv", index=False)
    return res


if __name__ == "__main__":
    run()
