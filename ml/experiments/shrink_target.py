"""Experimento 6 — entrenar con el target provincial "limpiado" hacia la serie nacional.

    y'_p,t = λ · y_p,t + (1 − λ) · y_nac,t        (solo en las filas de ENTRENAMIENTO)

La evaluación es SIEMPRE contra el target provincial crudo del año de test (sin limpiar), con la
tendencia recalculada sin ese año: si mejora, es porque el modelo aprendió mejor, no porque el
objetivo se volvió más fácil. λ = 1 es el modelo actual.

    ml/.venv/bin/python -m ml.experiments.shrink_target
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from ml.dataset import OUTPUT, TARGET
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


def loyo_shrunk(panel, climate, T, lam: float, block: int = 1) -> pd.DataFrame:
    half = block // 2
    base = panel.drop(columns=[TARGET, "y_anom_prev"], errors="ignore")
    req = [c for c in CORE.columns if c not in CORE.fill_zero]
    out = []
    for yr, tgt in T.items():
        held = set(range(yr - half, yr + half + 1))
        df = base.merge(tgt, on=["area_name", "year"])
        nat = df[df.area_name == "national"].set_index("year")[TARGET]
        train = df[~df.year.isin(held)].dropna(subset=req + [TARGET]).copy()
        prov = train.level == "province"
        train.loc[prov, TARGET] = lam * train.loc[prov, TARGET] + (1 - lam) * train.loc[prov, "year"].map(nat)
        train = train.dropna(subset=[TARGET])
        test = df[df.year == yr].dropna(subset=req + [TARGET])
        if test.empty:
            continue
        m = RidgeModel(CORE, climate).fit(train[CORE.columns], train[TARGET])
        out.append(test[["area_name", "year", "level", TARGET]].rename(columns={TARGET: "y_cv"})
                   .assign(pred=m.predict(test[CORE.columns])))
    return pd.concat(out, ignore_index=True)


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    res = {}
    for block in (1, 3):
        T = fold_targets(panel, value=OUTPUT, block=block)
        for lam in (1.0, 0.75, 0.5, 0.25):
            cv = loyo_shrunk(panel, climate, T, lam, block)
            n, p = cv[cv.level == "national"], cv[cv.level == "province"]
            r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"],
                 "prov_corr": score(p)["corr"], "prov_r2": score(p)["r2_oos"], "prov_rmse": score(p)["rmse"]}
            res[f"lambda {lam} | bloque {block}"] = r
            if verbose:
                print(f"λ = {lam:4.2f} bloque {block}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} | prov {r['prov_corr']:.3f}"
                      f" r2 {r['prov_r2']:.3f} rmse {r['prov_rmse']:.2f}", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp6_shrink_target.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
