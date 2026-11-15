"""Experimento 5 — clima provincial = promedio de sus cantones ponderado por superficie cultivada.

Hoy cada provincia usa el promedio de toda su superficie < 900 m. Aquí se calculan las features en
cada cantón (ml.cantons_predict, con su propia corrección de sesgo) y se promedian por provincia:

    x_prov(t) = Σ_c w_c · x_c(t),   w_c ∝ superficie de cultivo + árboles < 900 m (WorldCover)
                                    (variante: w_c iguales)

Solo cambia las provincias en 1983 y 1991–2025 (años con clima cantonal); la serie nacional no se toca.

    ml/.venv/bin/python -m ml.experiments.canton_weighted
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import numpy as np
import pandas as pd

from ml.cantons_predict import canton_features
from ml.dataset import OUTPUT
from ml.etl.cantons import norm
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"
FEATS = [c for c in CORE.inputs if c != "price_vs3_prev"]


def weighted_province_climate(weight: str) -> pd.DataFrame:
    feats, meta = canton_features()
    meta = meta.assign(pkey=meta.province.map(norm))
    w = (meta.set_index("area_name").crop_ha if weight == "cultivo"
         else pd.Series(1.0, index=meta.area_name))
    f = feats.merge(meta[["area_name", "pkey"]], on="area_name").assign(w=lambda d: d.area_name.map(w))
    def agg(g):
        out = {}
        for c in FEATS:
            ok = g[c].notna() & (g.w > 0)
            out[c] = np.average(g.loc[ok, c], weights=g.loc[ok, "w"]) if ok.any() else np.nan
        return pd.Series(out)
    return f.groupby(["pkey", "year"]).apply(agg, include_groups=False).reset_index()


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    T = fold_targets(panel, value=OUTPUT)
    T3 = fold_targets(panel, value=OUTPUT, block=3)
    res = {}
    for name in ("actual (provincia entera < 900 m)", "cultivo", "iguales"):
        p, c = panel.copy(), climate.copy()
        if name != "actual (provincia entera < 900 m)":
            wp = weighted_province_climate(name)
            for df in (p, c):
                key = df.area_name.map(norm)
                m = df.assign(pkey=key).merge(wp, on=["pkey", "year"], how="left", suffixes=("", "_w"))
                has = m[f"{FEATS[0]}_w"].notna().to_numpy() & (df.area_name != "national").to_numpy()
                for col in FEATS:
                    df[col] = df[col].astype(float)               # los conteos de días eran enteros
                    df.loc[has, col] = m.loc[has, f"{col}_w"].to_numpy()
        for blk, TT in ((1, T), (3, T3)):
            cv = loyo(p, partial(RidgeModel, CORE, c), CORE.columns, value=OUTPUT, targets=TT, block=blk,
                      allow_nan=CORE.fill_zero)
            n, pr = cv[cv.level == "national"], cv[cv.level == "province"]
            r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"], "prov_corr": score(pr)["corr"],
                 "prov_r2": score(pr)["r2_oos"], "prov_rmse": score(pr)["rmse"]}
            res[f"{name} | bloque {blk}"] = r
            if verbose:
                print(f"{name:36s} b{blk}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} | prov {r['prov_corr']:.3f}"
                      f" r2 {r['prov_r2']:.3f} rmse {r['prov_rmse']:.2f}", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp5_canton_weighted.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
