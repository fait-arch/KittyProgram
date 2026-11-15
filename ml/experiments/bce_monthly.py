"""Experimento 10 — exportaciones MENSUALES del Banco Central (1990–2026, subpartida 1801).

El total anual del BCE es el mismo dato que FAOSTAT (r = 1.00). Lo nuevo es: (1) el detalle mensual,
que permite medir la cosecha en la ventana que más depende de la lluvia de ene–jun (abr–sep), y
(2) 2025, que FAOSTAT aún no publica. Variantes del target nacional (1990→; antes, como hoy):

    A  actual                 media geom.(producción, exportaciones FAOSTAT)
    B  + BCE año calendario   media geom.(producción, exportaciones BCE)        (añade 2025)
    C  + BCE abr–sep          media geom.(producción, BCE abr–sep reescalado)
    D  3 medidas              media geom.(producción, FAOSTAT, BCE abr–sep reescalado)

Evaluación LOYO en la serie nacional contra su propio target y contra la producción sola.

    ml/.venv/bin/python -m ml.experiments.bce_monthly
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import numpy as np
import pandas as pd

from ml.config import DATA_PROCESSED
from ml.dataset import OUTPUT, TARGET
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


def bce_windows() -> pd.DataFrame:
    b = pd.read_parquet(DATA_PROCESSED / "bce_exports_monthly.parquet")
    full = b.groupby("year").agg(t=("t", "sum"), n=("month", "size"))
    cal = full.t[full.n == 12].rename("bce_year")
    w = b[b.month.between(4, 9)].groupby("year").agg(t=("t", "sum"), n=("month", "size"))
    aprsep = w.t[w.n == 6].rename("bce_aprsep")
    return pd.concat([cal, aprsep], axis=1)


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    bw = bce_windows()
    fao = pd.read_parquet(DATA_PROCESSED / "exports.parquet").set_index("year").export_beq_t
    nat = panel.level == "national"
    years = panel.loc[nat, "year"]
    prod = panel.loc[nat, "production_t"].to_numpy()
    f = years.map(fao).to_numpy()
    cal = years.map(bw.bce_year).to_numpy()
    ov = bw.dropna().index.intersection(fao.dropna().index)
    k_aps = float((fao.loc[ov] / bw.bce_aprsep.loc[ov]).mean())
    aps = years.map(bw.bce_aprsep).to_numpy() * k_aps
    geo = lambda *a: np.exp(np.nanmean(np.log(np.column_stack(a)), axis=1))
    variants = {
        "A actual (prod · FAOSTAT)": geo(prod, f),
        "B prod · BCE año calendario": geo(prod, np.where(np.isnan(cal), f, cal)),
        "C prod · BCE abr–sep": geo(prod, np.where(np.isnan(aps), f, aps)),
        "D prod · FAOSTAT · BCE abr–sep": geo(prod, f, aps),
    }
    prod_only = panel.assign(**{OUTPUT: np.where(nat, panel.production_t, panel[OUTPUT])})
    t_prod = fold_targets(prod_only[prod_only.level == "national"], value=OUTPUT)
    y_prod = {yr: float(t.set_index("year")[TARGET][yr]) for yr, t in t_prod.items()}
    res = {}
    for name, v in variants.items():
        p = panel.copy()
        p.loc[nat, OUTPUT] = v
        for blk in (1, 3):
            T = fold_targets(p, value=OUTPUT, block=blk)
            cv = loyo(p, partial(RidgeModel, CORE, climate), CORE.columns, value=OUTPUT, targets=T, block=blk,
                      allow_nan=CORE.fill_zero)
            n, pr = cv[cv.level == "national"], cv[cv.level == "province"]
            fair = n.assign(y_cv=n.year.map(y_prod)).dropna(subset=["y_cv"])
            ne = n[~n.year.isin([1983, 1998])]
            r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"], "sin_83_98": float(ne.y_cv.corr(ne.pred)),
                 "vs_prod_corr": score(fair)["corr"], "vs_prod_r2": score(fair)["r2_oos"],
                 "prov_corr": score(pr)["corr"], "pred_1998": float(n.set_index("year").pred[1998]),
                 "real_1998": float(n.set_index("year").y_cv[1998])}
            res[f"{name} | bloque {blk}"] = r
            if verbose:
                print(f"{name:32s} b{blk}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} sin83/98 {r['sin_83_98']:.3f} | "
                      f"vs producción {r['vs_prod_corr']:.3f} r2 {r['vs_prod_r2']:.3f} | prov {r['prov_corr']:.3f} | "
                      f"1998 {r['pred_1998']:.0f} (real {r['real_1998']:.0f})", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp10_bce_monthly.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
