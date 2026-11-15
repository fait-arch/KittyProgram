"""Experimento 9 — aprender también de Colombia y Perú (más eventos de lluvia extrema).

Mismo modelo, mismas fórmulas y misma corrección de sesgo; cada país entra como un área más con su
producción FAOSTAT (anomalía respecto a su tendencia, sin el año de test) y el clima ene–jun de sus
zonas cacaoteras (ml.experiments.intl_climate). La validación es SOLO sobre Ecuador (nacional y
provincias): ¿los otros países le enseñan algo al modelo de Ecuador?

    ml/.venv/bin/python -m ml.experiments.multicountry
"""
from __future__ import annotations

import json
import re
import warnings
from functools import partial

import numpy as np
import pandas as pd

from ml.config import DATA_PROCESSED
from ml.dataset import OUTPUT, TARGET, add_target, load_price_features
from ml.etl.production import FAO_DIR, _read_fao_csv
from ml.features import BiasCorrection, build_features
from ml.model import CORE, RidgeModel
from ml.train import load_data, score
from ml.validation import fold_targets, loyo

RESULTS = __import__("pathlib").Path(__file__).parent / "results"
COUNTRIES = {"colombia": "Colombia", "peru": "Peru"}


def fao_production() -> pd.DataFrame:
    df = _read_fao_csv(FAO_DIR / "Production_Crops_Livestock_E_Americas.zip")
    df = df[df.Area.isin(COUNTRIES.values()) & (df.Item == "Cocoa beans") & (df.Element == "Production")]
    yc = [c for c in df.columns if re.fullmatch(r"Y\d{4}", c)]
    long = df.melt(id_vars=["Area"], value_vars=yc, var_name="year", value_name="production_t")
    long["year"] = long.year.str[1:].astype(int)
    inv = {v: k for k, v in COUNTRIES.items()}
    return long.assign(area_name=long.Area.map(inv)).dropna(subset=["production_t"])[["area_name", "year", "production_t"]]


def intl_features() -> pd.DataFrame:
    daily = pd.read_parquet(DATA_PROCESSED / "climate_daily_intl.parquet")
    bc = BiasCorrection.fit(daily, pd.read_parquet(DATA_PROCESSED / "worldclim_intl.parquet"),
                            pd.read_parquet(DATA_PROCESSED / "area_meta_intl.parquet"))
    return build_features(daily, bc).merge(load_price_features(), on="year", how="left")


def run(verbose=True):
    warnings.filterwarnings("ignore")
    panel, climate = load_data()
    feats = intl_features()
    prod = fao_production()
    other = prod.merge(feats, on=["area_name", "year"], how="inner").assign(level="other_country")
    other[OUTPUT] = other.production_t
    other = add_target(other, value=OUTPUT)
    if verbose:
        o = other.copy()
        for c in ("rain_total", "saturated_days", "fav_days_phytophthora", TARGET):
            o[c] = o[c] - o.groupby("area_name")[c].transform("mean")
        for a, g in o.groupby("area_name"):
            print(f"{a}: {len(g)} años {g.year.min()}–{g.year.max()} | corr target con lluvia {g[TARGET].corr(g.rain_total):.2f}, "
                  f"suelo saturado {g[TARGET].corr(g.saturated_days):.2f}, días favorables {g[TARGET].corr(g.fav_days_phytophthora):.2f}")
            w = g.nsmallest(3, TARGET)[["year", TARGET, "rain_total"]].round(0).values.tolist()
            print("   peores años [año, anomalía %, anomalía lluvia mm]:", w)
    res = {}
    cols = list(dict.fromkeys(panel.columns.tolist()))
    for name, add in (("solo Ecuador (actual)", []), ("+ Colombia", ["colombia"]), ("+ Perú", ["peru"]),
                      ("+ Colombia + Perú", ["colombia", "peru"])):
        p = pd.concat([panel, other[other.area_name.isin(add)].reindex(columns=cols)], ignore_index=True)
        c = pd.concat([climate, feats[feats.area_name.isin(add)]], ignore_index=True)
        for blk in (1, 3):
            T = fold_targets(p, value=OUTPUT, block=blk)
            cv = loyo(p, partial(RidgeModel, CORE, c), CORE.columns, value=OUTPUT, targets=T, block=blk,
                      allow_nan=CORE.fill_zero)
            n, pr = cv[cv.level == "national"], cv[cv.level == "province"]
            ne = n[~n.year.isin([1983, 1998])]
            r = {"nat_corr": score(n)["corr"], "nat_r2": score(n)["r2_oos"], "nat_sin_83_98": float(ne.y_cv.corr(ne.pred)),
                 "prov_corr": score(pr)["corr"], "prov_r2": score(pr)["r2_oos"],
                 "pred_1983": float(n.set_index("year").pred[1983]), "pred_1998": float(n.set_index("year").pred[1998])}
            res[f"{name} | bloque {blk}"] = r
            if verbose:
                print(f"{name:24s} b{blk}: nat {r['nat_corr']:.3f} r2 {r['nat_r2']:.3f} sin83/98 {r['nat_sin_83_98']:.3f} | "
                      f"prov {r['prov_corr']:.3f} r2 {r['prov_r2']:.3f} | 1983 {r['pred_1983']:.0f} 1998 {r['pred_1998']:.0f}", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "exp9_multicountry.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    run()
