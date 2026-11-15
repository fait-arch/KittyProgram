"""Experimento 7 — importaciones de la UE desde Ecuador (Eurostat Comext, mensual 1988→) como
tercera medida de la cosecha nacional.

    eu_beq(t) = grano + 1.25·pasta + 1.33·manteca + 1.18·polvo           (equivalente de grano, ICCO)
    target_nac = media geométrica de {producción FAOSTAT, exportaciones FAOSTAT, eu_beq}  (cuando existe)

Variantes de eu_beq: año calendario, o solo abr–sep (cosecha principal + ~1 mes de transporte).
Evaluación en la serie nacional contra (a) su propio target y (b) la producción sola (prueba justa).

    ml/.venv/bin/python -m ml.experiments.eu_imports
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import numpy as np
import pandas as pd

from ml.config import DATA_RAW, DATA_PROCESSED
from ml.dataset import OUTPUT, TARGET
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"
BEQ = {"1801": 1.0, "1803": 1.25, "1804": 1.33, "1805": 1.18}


def eu_series() -> pd.DataFrame:
    df = pd.read_csv(DATA_RAW / "eurostat" / "eu_imports_from_ecuador_monthly.csv", dtype={"product": str})
    df["beq"] = df.t * df["product"].map(BEQ)
    m = df.groupby(["year", "month"]).beq.sum().reset_index()
    full = m.groupby("year").beq.sum().rename("eu_year")
    main = m[m.month.between(4, 9)].groupby("year").beq.sum().rename("eu_aprsep")
    return pd.concat([full, main], axis=1).loc[1988:2025].reset_index()


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    eu = eu_series()
    exp = pd.read_parquet(DATA_PROCESSED / "exports.parquet")[["year", "export_beq_t"]]
    nat = panel.level == "national"
    base = panel.merge(eu, on="year", how="left").merge(exp, on="year", how="left", suffixes=("", "_e"))
    expo = base["export_beq_t_e"] if "export_beq_t_e" in base else base["export_beq_t"]
    prod_only = panel.assign(**{OUTPUT: np.where(nat, panel.production_t, panel[OUTPUT])})
    t_prod = fold_targets(prod_only[prod_only.level == "national"], value=OUTPUT)
    y_prod = {yr: float(t.set_index("year")[TARGET][yr]) for yr, t in t_prod.items()}
    variants = {"actual (prod · export)": None, "+ UE año completo": "eu_year", "+ UE abr–sep": "eu_aprsep"}
    res = {}
    for name, col in variants.items():
        p = panel.copy()
        if col:
            parts = np.column_stack([base.production_t, expo, base[col]])
            logs = np.log(parts)
            geo = np.exp(np.nanmean(logs, axis=1))
            p.loc[nat, OUTPUT] = geo[nat.to_numpy()]
        cv = loyo(p, partial(RidgeModel, CORE, climate), CORE.columns, value=OUTPUT,
                  targets=fold_targets(p, value=OUTPUT), allow_nan=CORE.fill_zero)
        n = cv[cv.level == "national"]
        fair = n.assign(y_cv=n.year.map(y_prod)).dropna(subset=["y_cv"])
        ne = n[~n.year.isin([1983, 1998])]
        res[name] = {"corr": score(n)["corr"], "r2": score(n)["r2_oos"], "rmse": score(n)["rmse"],
                     "sin_83_98": float(ne.y_cv.corr(ne.pred)),
                     "vs_produccion_corr": score(fair)["corr"], "vs_produccion_r2": score(fair)["r2_oos"],
                     "pred_1998": float(n.set_index("year").pred[1998]), "real_1998": float(n.set_index("year").y_cv[1998])}
        if verbose:
            r = res[name]
            print(f"{name:24s} nat corr {r['corr']:.3f} r2 {r['r2']:.3f} | sin 83/98 {r['sin_83_98']:.3f} | vs producción "
                  f"corr {r['vs_produccion_corr']:.3f} r2 {r['vs_produccion_r2']:.3f} | 1998 {r['pred_1998']:.0f} (real {r['real_1998']:.0f})", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp7_eu_imports.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
