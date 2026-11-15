"""Experimento 1 — ¿las horas de hoja mojada (ERA5-Land horario) mejoran el modelo?

Variantes (todas como anomalía z del área, signo −: más horas mojadas → más enfermedad):
    + infect_h            añadida al modelo actual
    infect_h en lugar de fav_days_phytophthora   (fórmula horaria vs diaria)
    + night_wet_h, + wet_h

    ml/.venv/bin/python -m ml.experiments.wetness_model
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import pandas as pd

from ml.config import DATA_PROCESSED
from ml.dataset import OUTPUT, TARGET
from ml.model import CORE, FeatureSpec, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


def with_vars(add=(), drop=()):
    anom = tuple(c for c in CORE.anom if c not in drop) + tuple(add)
    signs = tuple((c, s) for c, s in CORE.signs if c not in drop) + tuple((c, -1) for c in add)
    return FeatureSpec(anom=anom, hinges=CORE.hinges, signs=signs, fill_zero=CORE.fill_zero)


VARIANTS = {
    "modelo actual": CORE,
    "+ horas de infección": with_vars(add=("infect_h",)),
    "horas de infección en vez de días fav.": with_vars(add=("infect_h",), drop=("fav_days_phytophthora",)),
    "+ horas mojadas de noche": with_vars(add=("night_wet_h",)),
    "+ horas mojadas": with_vars(add=("wet_h",)),
}


def run(verbose: bool = True) -> dict:
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    hw = pd.read_parquet(DATA_PROCESSED / "hourly_wetness.parquet")
    panel = panel.merge(hw, on=["area_name", "year"], how="left")
    climate = climate.merge(hw, on=["area_name", "year"], how="left")
    if verbose:
        w = panel.copy()
        for c in ("infect_h", "night_wet_h", "wet_h", "fav_days_phytophthora", TARGET):
            w[c] = w[c] - w.groupby("area_name")[c].transform("mean")
        print("corr (dentro de área) con el target:",
              w[["infect_h", "night_wet_h", "wet_h", "fav_days_phytophthora"]].corrwith(w[TARGET]).round(2).to_dict())
        print("corr infect_h vs fav_days_phytophthora:", round(w.infect_h.corr(w.fav_days_phytophthora), 2))
    res = {}
    for blk in (1, 3):
        T = fold_targets(panel, value=OUTPUT, block=blk)
        for name, sp in VARIANTS.items():
            cv = loyo(panel, partial(RidgeModel, sp, climate), sp.columns, value=OUTPUT, targets=T,
                      block=blk, allow_nan=sp.fill_zero)
            n, p = cv[cv.level == "national"], cv[cv.level == "province"]
            res[f"{name} | bloque {blk}"] = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"],
                                             "nat_rmse": score(n)["rmse"], "prov_corr": score(p)["corr"],
                                             "prov_r2": score(p)["r2_oos"]}
            if verbose:
                r = res[f"{name} | bloque {blk}"]
                print(f"{name:42s} b{blk}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} rmse {r['nat_rmse']:.2f}"
                      f" | prov {r['prov_corr']:.3f} r2 {r['prov_r2']:.3f}", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp1_wetness.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
