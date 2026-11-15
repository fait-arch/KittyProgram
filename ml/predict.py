"""Predicciones por área y escenario (Fase 5): lo que el equipo carga en Supabase.

    ml/.venv/bin/python -m ml.predict

Lee el bundle (`artifacts/cacao_loss_v1.joblib`) y escribe en `artifacts/`:

    loss_predictions_v1.csv / .parquet   una fila por área × escenario, columnas de la tabla
                                          `loss_predictions` (+ extras: y_anom_pct, evidence…)
    model_version_v1.json                 fila para la tabla `model_versions`

Pérdida de un escenario = media de las pérdidas predichas para cada año del escenario
(`scenario_years`): así un escenario que mezcla años normales y extremos no se diluye en un
"clima promedio" que nunca ocurre.

    loss_t   = exposed_ha · expected_yield_t_ha · loss_pct / 100
    loss_usd = loss_t · price_usd_t
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from .config import ARTIFACTS, DATA_PROCESSED
from .dataset import OUTPUT
from .model import EXCLUDE_AREAS, ID_COLS, risk_class
from .scenarios import load_climate

VERSION = "v1"
CROP = "cacao"


def load_bundle(path=None) -> dict:
    return joblib.load(path or ARTIFACTS / f"cacao_loss_{VERSION}.joblib")


def exposure(panel: pd.DataFrame) -> pd.DataFrame:
    """Último año disponible de cada área: hectáreas expuestas y rendimiento esperado (tendencia).

    Provincias: el target es t por ha SEMBRADA → exposed_ha = ha sembradas.
    Nacional: la tendencia es de producción (t) → rendimiento = tendencia / ha cosechadas.
    """
    last = panel.sort_values("year").groupby("area_name").tail(1).set_index("area_name")
    nat = last.index == "national"
    exposed = np.where(nat, last.harvested_ha, last.planted_ha)
    expected = np.where(nat, last.trend / last.harvested_ha, last.trend)
    return pd.DataFrame({"exposed_ha": exposed, "expected_yield_t_ha": expected,
                         "exposure_year": last.year})


def latest_price() -> tuple[float, int]:
    p = pd.read_parquet(DATA_PROCESSED / "prices.parquet").dropna(subset=["price_usd_t"])
    r = p.sort_values("year").iloc[-1]
    return float(r.price_usd_t), int(r.year)


def predict_scenarios(bundle: dict, climate: pd.DataFrame, areas: list[str]) -> pd.DataFrame:
    m = bundle["model"]
    cols = m.features
    rows = []
    for area in areas:
        for sc, years in bundle["scenario_years"].items():
            X = climate[(climate.area_name == area) & climate.year.isin(years)][ID_COLS + cols]
            X = X.dropna(subset=[c for c in cols if c not in m.model.spec.fill_zero])
            if X.empty:
                continue
            out = m.predict(X)
            contrib = m.model.contributions(X.reset_index(drop=True)).mean()
            mean_x = X[cols].mean().fillna(0.0)
            factors = sorted(({"feature": k, "value": round(float(mean_x[k]), 2),
                               "contribution_pct": round(float(-v), 2)} for k, v in contrib.items()),
                             key=lambda d: -abs(d["contribution_pct"]))[:5]
            loss = float(out.loss_pct.mean())
            rows.append({
                "area_name": area, "crop_id": CROP, "scenario_id": sc,
                "loss_pct": round(loss, 2),
                "loss_pct_low": round(float(out.loss_p10.mean()), 2),
                "loss_pct_high": round(float(out.loss_p90.mean()), 2),
                "risk_class": risk_class(loss), "top_factors": factors,
                "y_anom_pct": round(float(out.y_anom_pct.mean()), 2),
                "loss_pct_max_year": round(float(out.loss_pct.max()), 2),
                "evidence": out.evidence.iloc[0], "extrapolated": bool(out.extrapolated.any()),
                "scenario_years": [int(y) for y in X.year], "model_version": bundle["version"],
            })
    return pd.DataFrame(rows)


def model_version_row(bundle: dict) -> dict:
    """Fila de `model_versions` con las métricas mínimas del contrato del backend."""
    v = bundle["metrics"]
    nat = v["models"]["ridge"]["national"]
    base = v["models"]["base_normal"]["national"]
    ev = {str(e["year"]): bool(e["pred"] < -10) for e in v["nino_events_national"]
          if e["y_cv"] < -10}
    m = bundle["model"]
    return {
        "name": bundle["version"], "crop_id": CROP, "target": "production_anomaly_pct",
        "algorithm": "ridge_sign_constrained", "features": bundle["features"],
        "hyperparams": {"lambda": float(m.model.alpha_), "rain_hinge_sd": 2.0, "weights": "1/s_a^2"},
        "cv_scheme": "leave_one_year_out",
        "metrics": {"mae": nat["mae"], "mae_baseline": base["mae"],
                    "rmse": nat["rmse"], "rmse_baseline": base["rmse"],
                    "skill_vs_baseline": 1 - nat["rmse"] / base["rmse"],
                    "corr": nat["corr"], "r2_oos": nat["r2_oos"],
                    "interval_coverage_p10_p90": nat["coverage_80"],
                    "nino_years_hit": ev, "best": "ridge",
                    "province_skill": v["models"]["ridge"]["province"]["r2_oos"],
                    "permutation_p": ((v.get("permutation_test") or {}).get("national") or {}).get("p_value"),
                    "permutation_p_province": ((v.get("permutation_test") or {}).get("province") or {}).get("p_value")},
        "train_start_year": m.meta["years"][0], "train_end_year": m.meta["years"][1],
        "n_samples": int(v["models"]["ridge"]["national"]["n"] + v["models"]["ridge"]["province"]["n"]),
        "artifact_path": f"ml/artifacts/cacao_loss_{VERSION}.joblib", "is_active": True,
    }


def run(save: bool = True, verbose: bool = True) -> pd.DataFrame:
    bundle = load_bundle()
    panel = pd.read_parquet(DATA_PROCESSED / "training_panel.parquet")
    panel = panel[~panel.area_name.isin(EXCLUDE_AREAS)]
    climate = load_climate()
    areas = sorted(set(panel.area_name) & set(bundle["model"].noise_scale))
    pred = predict_scenarios(bundle, climate, areas)
    exp = exposure(panel)
    price, price_year = latest_price()
    pred = pred.merge(exp, left_on="area_name", right_index=True, how="left")
    pred["loss_t"] = (pred.exposed_ha * pred.expected_yield_t_ha * pred.loss_pct / 100).round(1)
    pred["price_usd_t"], pred["price_year"] = price, price_year
    pred["loss_usd"] = (pred.loss_t * price).round(0)
    order = ["model_version", "area_name", "crop_id", "scenario_id", "loss_pct", "loss_pct_low",
             "loss_pct_high", "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd",
             "risk_class", "top_factors", "y_anom_pct", "loss_pct_max_year", "evidence", "extrapolated",
             "scenario_years", "exposure_year", "price_year"]
    pred = pred[order]
    if verbose:
        t = pred.pivot(index="area_name", columns="scenario_id", values="loss_pct")
        print("Pérdida esperada (%) por área y escenario:")
        print(t[[c for c in bundle["scenario_years"] if c in t]].round(1).to_string())
        print("\nAños de cada escenario:", bundle["scenario_years"])
        nat = pred[pred.area_name == "national"].set_index("scenario_id")
        print("\nNacional (t y USD perdidos):")
        print(nat[["loss_pct", "loss_pct_low", "loss_pct_high", "loss_t", "loss_usd"]].round(1).to_string())
    if save:
        out = pred.assign(top_factors=pred.top_factors.map(json.dumps),
                          scenario_years=pred.scenario_years.map(json.dumps))
        out.to_parquet(ARTIFACTS / f"loss_predictions_{VERSION}.parquet", index=False)
        out.to_csv(ARTIFACTS / f"loss_predictions_{VERSION}.csv", index=False)
        (ARTIFACTS / f"model_version_{VERSION}.json").write_text(
            json.dumps(model_version_row(bundle), indent=2, ensure_ascii=False))
        if verbose:
            print(f"\nGuardado: artifacts/loss_predictions_{VERSION}.csv/.parquet y model_version_{VERSION}.json")
    return pred


def main():
    run()


if __name__ == "__main__":
    main()
