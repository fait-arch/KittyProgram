"""Experimento 8 — limpieza robusta de los datos al entrenar (evaluación siempre con el dato crudo).

    Huber (IRLS): w_i ← w_i · min(1, c / |r_i / s|)   repetido 5 veces, c = 1.345 (95 % de eficiencia)
                  → los años con error enorme (crisis, errores de la estadística) pierden peso solos
    Recorte:      y_train ← clip(y, −k·s_a, +k·s_a)    k = 2 o 2.5 desviaciones del área

    ml/.venv/bin/python -m ml.experiments.robust
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, RidgeCV

from ml.dataset import OUTPUT
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


class HuberRidge(RidgeModel):
    def __init__(self, spec=CORE, climate=None, c=1.345, iters=5):
        super().__init__(spec, climate)
        self.c, self.iters = c, iters

    def fit(self, X, y):
        Z, w0 = self._prepare(X, y)
        self.cols_ = list(Z.columns)
        from sklearn.preprocessing import StandardScaler
        self.scaler_ = StandardScaler().fit(Z)
        S = self.scaler_.transform(Z)
        sg = np.array([self.spec.sign(c) for c in self.cols_])
        A = S * np.where(sg == 0, 1, sg)
        w = w0.copy()
        self.alpha_ = float(RidgeCV(alphas=np.logspace(-1, 3, 25)).fit(S, y, sample_weight=w).alpha_)
        for _ in range(self.iters):
            nn = Ridge(alpha=self.alpha_, positive=True, tol=1e-10).fit(A, y, sample_weight=w)
            r = (y.to_numpy() - nn.predict(A)) * np.sqrt(w0)          # residuo en escala homogénea
            s = 1.4826 * np.median(np.abs(r - np.median(r)))           # MAD
            w = w0 * np.minimum(1.0, self.c / np.maximum(np.abs(r) / s, 1e-9))
        self.coef_ = nn.coef_ * np.where(sg == 0, 1, sg)
        self.intercept_ = float(nn.intercept_)
        self.huber_w_ = pd.Series(w / w0, index=X.index)
        return self


class ClippedRidge(RidgeModel):
    def __init__(self, spec=CORE, climate=None, k=2.0):
        super().__init__(spec, climate)
        self.k = k

    def fit(self, X, y):
        s = y.groupby(X.area_name.to_numpy()).transform("std").to_numpy()
        return super().fit(X, pd.Series(np.clip(y.to_numpy(), -self.k * s, self.k * s), index=y.index))


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    res = {}
    for blk in (1, 3):
        T = fold_targets(panel, value=OUTPUT, block=blk)
        for name, mk in [("actual", partial(RidgeModel, CORE, climate)),
                         ("Huber c=1.345", partial(HuberRidge, CORE, climate)),
                         ("Huber c=2.5", partial(HuberRidge, CORE, climate, 2.5)),
                         ("recorte ±2 sd", partial(ClippedRidge, CORE, climate, 2.0)),
                         ("recorte ±2.5 sd", partial(ClippedRidge, CORE, climate, 2.5))]:
            cv = loyo(panel, mk, CORE.columns, value=OUTPUT, targets=T, block=blk, allow_nan=CORE.fill_zero)
            n, p = cv[cv.level == "national"], cv[cv.level == "province"]
            r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"], "prov_corr": score(p)["corr"],
                 "prov_r2": score(p)["r2_oos"], "pred_1998": float(n.set_index("year").pred[1998])}
            res[f"{name} | bloque {blk}"] = r
            if verbose:
                print(f"{name:16s} b{blk}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} | prov {r['prov_corr']:.3f} "
                      f"r2 {r['prov_r2']:.3f} | 1998 {r['pred_1998']:.0f}", flush=True)
    m = HuberRidge(CORE, climate).fit(panel[CORE.columns], panel["y_anom_pct"])
    low = panel.assign(w=m.huber_w_.to_numpy()).nsmallest(10, "w")[["area_name", "year", "y_anom_pct", "w"]]
    if verbose:
        print("\nAños a los que Huber les quita más peso (datos raros):")
        print(low.round(2).to_string(index=False))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp8_robust.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
