"""Experimento 4 — alerta temprana: predecir la temporada ene–jun ANTES de que empiece.

Tres momentos del año anterior, solo con lo que ya se conoce en esa fecha:

    octubre (t−1)   Niño 1+2 y ONI de ago–oct                       → 3 meses antes
    enero   (t)     + Niño 1+2 de oct–dic y lluvia/suelo oct–dic del área
    julio   (t)     modelo actual (clima ene–jun observado)          → al final de la temporada

    ŷ = b0 + Σ β·t + γ·max(0, Niño1+2 − 1 °C)     (Ridge con signos: mar caliente / lluvia → pérdida)

    ml/.venv/bin/python -m ml.experiments.early_warning
"""
from __future__ import annotations

import json
import warnings
from functools import partial

import pandas as pd

from ml.config import DATA_PROCESSED
from ml.dataset import OUTPUT
from ml.experiments.probability import BAD, Climatology, ridge_probability, evaluate
from ml.model import CORE, FeatureSpec, RidgeModel
from ml.train import KEY, load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"


def enso_leads() -> pd.DataFrame:
    """Índices ENSO del año anterior por estación, indexados por el año de la temporada."""
    m = pd.read_parquet(DATA_PROCESSED / "enso_monthly.parquet")
    m = m.assign(y=m.month_date.dt.year + 1, mo=m.month_date.dt.month)
    def season(months, col, name):
        return m[m.mo.isin(months)].groupby("y")[col].mean().rename(name)
    return pd.concat([season([8, 9, 10], "nino12_anom", "n12_aso"), season([8, 9, 10], "oni", "oni_aso"),
                      season([10, 11, 12], "nino12_anom", "n12_ond"), season([10, 11, 12], "oni", "oni_ond")],
                      axis=1).rename_axis("year").reset_index()


LEADS = {
    "octubre (3 meses antes)": FeatureSpec(
        anom=(), raw=("n12_aso", "oni_aso"), hinges=(("n12_aso", 1.0),),
        signs=(("n12_aso", -1), ("oni_aso", -1))),
    "enero (al empezar)": FeatureSpec(
        anom=("rain_prev_ond", "fav_phyto_prev_ond"), raw=("n12_ond", "oni_ond"),
        hinges=(("n12_ond", 1.0),),
        signs=(("n12_ond", -1), ("oni_ond", -1), ("rain_prev_ond", -1), ("fav_phyto_prev_ond", -1))),
    "julio (modelo actual)": CORE,
}


def run(verbose: bool = True) -> dict:
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    leads = enso_leads()
    panel = panel.merge(leads, on="year", how="left")
    T = fold_targets(panel, value=OUTPUT)
    res, cvs = {}, {}
    for name, sp in LEADS.items():
        cv = loyo(panel, partial(RidgeModel, sp, climate), sp.columns, value=OUTPUT, targets=T,
                  allow_nan=sp.fill_zero)
        cv = ridge_probability(cv)
        clim = loyo(panel, Climatology, sp.columns, value=OUTPUT, targets=T, allow_nan=sp.fill_zero)
        cv = cv.merge(clim[KEY + ["pred"]].rename(columns={"pred": "p_clim"}), on=KEY)
        cvs[name] = cv
        res[name] = {}
        for lvl in ("national", "province"):
            d = cv[cv.level == lvl]
            s = score(d.drop(columns=["prob", "p_clim"]))
            res[name][lvl] = {"corr": s["corr"], "r2_oos": s["r2_oos"], "rmse": s["rmse"],
                              **{f"prob_{k}": v for k, v in evaluate(d, "prob").items()
                                 if k in ("brier_skill", "auc")}}
    if verbose:
        for lvl in ("national", "province"):
            print(f"\n{lvl}")
            print(pd.DataFrame({k: v[lvl] for k, v in res.items()}).T.round(3).to_string())
        print("\nNacional: pérdida predicha / probabilidad de año malo por momento de aviso")
        rows = {}
        for name, cv in cvs.items():
            n = cv[cv.level == "national"].set_index("year")
            rows[name] = [f"{n.pred[y]:.0f}% / {n.prob[y]:.0%}" for y in (1983, 1987, 1998, 2016, 2024)]
        real = cvs["julio (modelo actual)"]
        real = real[real.level == "national"].set_index("year").y_cv
        rows["REAL"] = [f"{real[y]:.0f}%" for y in (1983, 1987, 1998, 2016, 2024)]
        print(pd.DataFrame(rows, index=[1983, 1987, 1998, 2016, 2024]).T.to_string())
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp4_early_warning.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
