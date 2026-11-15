"""Experimento 11 — ¿el modelo sigue funcionando si MODIS se apaga? (VIIRS calibrado como respaldo)

Se simula que MODIS no existe desde 2012: el verdor ene–jun de 2012–2025 sale solo de VIIRS
calibrado a escala MODIS (features.fit_evi_calibration). Se compara la validación LOYO.

    ml/.venv/bin/python -m ml.experiments.viirs_backup
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import pandas as pd

from ml.dataset import OUTPUT, fit_bias_correction, load_price_features
from ml.features import build_features
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    bc, daily = fit_bias_correction()
    sim = daily.copy()
    sim.loc[sim.date.dt.year >= 2012, "modis_evi"] = float("nan")
    f_sim = build_features(sim, bc).merge(load_price_features(), on="year", how="left")
    f_real = build_features(daily, bc).merge(load_price_features(), on="year", how="left")
    res = {}
    T = fold_targets(panel, value=OUTPUT)
    for name, f in (("MODIS (actual)", f_real), ("solo VIIRS desde 2012", f_sim)):
        p = panel.drop(columns=["evi_jan_jun"]).merge(f[["area_name", "year", "evi_jan_jun"]], on=["area_name", "year"], how="left")
        c = climate.drop(columns=["evi_jan_jun"]).merge(f[["area_name", "year", "evi_jan_jun"]], on=["area_name", "year"], how="left")
        cv = loyo(p, partial(RidgeModel, CORE, c), CORE.columns, value=OUTPUT, targets=T, allow_nan=CORE.fill_zero)
        n, pr = cv[cv.level == "national"], cv[cv.level == "province"]
        n12, p12 = n[n.year >= 2012], pr[pr.year >= 2012]
        r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"], "prov_corr": score(pr)["corr"],
             "prov_r2": score(pr)["r2_oos"], "prov_corr_2012_2025": float(p12.y_cv.corr(p12.pred)),
             "nat_corr_2012_2025": float(n12.y_cv.corr(n12.pred))}
        res[name] = r
        if verbose:
            print(f"{name:24s}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} | prov {r['prov_corr']:.3f} r2 {r['prov_r2']:.3f}"
                  f" | 2012–2025: nat {r['nat_corr_2012_2025']:.3f} prov {r['prov_corr_2012_2025']:.3f}", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp11_viirs_backup.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
