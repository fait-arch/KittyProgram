"""Fase 5: interfaz para el backend (ml.inference), escenarios y predicciones por lote.

Comprueba el contrato de docs/backend/03-integracion-ml.md (rama emilio/backend):
bundle dict, `adjust_features(features, adjust, area_ctx)` y `predict(bundle, features)`.
Usa el bundle entrenado (`python -m ml.train`) y las predicciones (`python -m ml.predict`).
"""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.config import ARTIFACTS
from ml.inference import adjust_features, attach_area_ids, predict, register_area
from ml.predict import VERSION
from ml.scenarios import SCENARIOS, analog_years, load_climate

CONTRACT_KEYS = {"loss_pct", "loss_pct_low", "loss_pct_high", "top_factors", "out_of_range"}


@pytest.fixture(scope="module")
def bundle():
    path = ARTIFACTS / f"cacao_loss_{VERSION}.joblib"
    if not path.exists():
        pytest.skip("modelo no entrenado: ml/.venv/bin/python -m ml.train")
    return joblib.load(path)


@pytest.fixture
def fresh(bundle):
    return joblib.load(ARTIFACTS / f"cacao_loss_{VERSION}.joblib")   # copia que se puede modificar


def base(bundle, area="national", sc="normal"):
    return dict(bundle["scenario_features"][area][sc])


# ── Bundle ────────────────────────────────────────────────────────────────────────────
def test_bundle_matches_backend_contract(bundle):
    for k in ("version", "features", "model", "feature_ranges", "feature_means", "explain",
              "sklearn_version", "scenario_features"):
        assert k in bundle, k
    assert bundle["version"] == f"cacao_loss_{VERSION}"
    assert set(bundle["feature_ranges"]) == set(bundle["features"])
    for area, scs in bundle["scenario_features"].items():
        assert set(SCENARIOS) <= set(scs), area
        for v in scs.values():
            required = set(bundle["features"]) - set(bundle["model"].model.spec.fill_zero)
            assert required <= set(v) and v["_area"] == area and v["_sens"]


def test_backend_flow_what_if(bundle):
    """Lo que hace BACK/app/services/predictor.what_if: vector base → sliders → predict."""
    f0 = base(bundle, "Los Rios", "normal")
    r0 = predict(bundle, f0)
    r1 = predict(bundle, adjust_features(f0, {"rain_delta_pct": 80}, {}))
    assert CONTRACT_KEYS <= set(r0) and r0["area_used"] == "Los Rios"
    assert r1["loss_pct"] > r0["loss_pct"]
    assert r0["loss_pct_low"] <= r0["loss_pct"] <= r0["loss_pct_high"]
    tf = r1["top_factors"][0]
    assert set(tf) == {"feature", "value", "contribution_pct"} and tf["contribution_pct"] > 0
    json.dumps(r1)


def test_predict_matches_batch_model(bundle):
    clim = load_climate()
    row = clim[(clim.area_name == "national") & (clim.year == 1998)].iloc[0]
    r = predict(bundle, {**row.to_dict(), "_area": "national"})
    direct = bundle["model"].predict(pd.DataFrame([row])[["area_name", "year"] + bundle["features"]])
    assert r["loss_pct"] == pytest.approx(direct.loss_pct.iloc[0]) and r["loss_pct"] > 25


def test_area_fallbacks(bundle):
    f = base(bundle)
    f.pop("_area")
    assert predict(bundle, f)["area_used"] == "national"
    assert predict(bundle, {**f, "_province": "Guayas"})["area_used"] == "Guayas"
    assert predict(bundle, {**f, "_area": "?", "_province": "Guayas"})["area_used"] == "Guayas"
    with pytest.raises(ValueError):
        predict(bundle, {"rain_total": 1000})


# ── Sliders ──────────────────────────────────────────────────────────────────────────
def test_sliders_neutral_and_rain(bundle):
    f0 = base(bundle, "Guayas")
    assert adjust_features(f0, {}, {}) == f0                          # sin sliders, sin cambios
    f1 = adjust_features(f0, {"rain_delta_pct": 20}, {})
    assert f1["rain_total"] == pytest.approx(f0["rain_total"] * 1.2)
    assert f1["saturated_days"] > f0["saturated_days"]                 # la lluvia arrastra al suelo
    assert f1["fav_days_phytophthora"] > f0["fav_days_phytophthora"]
    assert f1["solar_mean"] < f0["solar_mean"]                         # más nubes
    f2 = adjust_features(f0, {"rain_delta_pct": 1000}, {})
    assert f2["saturated_days"] <= 181 and f2["fav_days_phytophthora"] <= 181


def test_nino_slider_raises_rain_and_loss(bundle):
    f0 = base(bundle)
    s = f0["_sens"]
    assert s["mm_per_nino12"] > 0 and s["mm_per_oni"] > 0             # El Niño trae lluvia a la costa
    f1 = adjust_features(f0, {"nino12_anom": 3.0}, {})
    assert f1["nino12_jan_jun"] == 3.0 and f1["rain_total"] > f0["rain_total"]
    losses = [predict(bundle, adjust_features(f0, {"nino12_anom": n}, {}))["loss_pct"]
              for n in (-1, 0, 1, 2, 3, 4)]
    assert np.all(np.diff(losses) >= -1e-9) and losses[-1] > losses[0]
    f2 = adjust_features(f0, {"oni": 2.5}, {})
    assert f2["oni_jan_jun"] == 2.5 and f2["rain_total"] > f0["rain_total"]


def test_temperature_slider_only_moves_fav_days(bundle):
    f0 = base(bundle, "Manabi")
    f1 = adjust_features(f0, {"temp_delta_c": 2.0}, {})
    assert f1["rain_total"] == f0["rain_total"] and f1["saturated_days"] == f0["saturated_days"]
    assert f1["fav_days_phytophthora"] != f0["fav_days_phytophthora"]


# ── Áreas nuevas (cantones) e ids de Supabase ────────────────────────────────────────
def test_attach_area_ids(fresh):
    attach_area_ids(fresh, {"uuid-guayas": "Guayas"})
    f = {**base(fresh, "uuid-guayas"), "_area": "uuid-guayas"}
    assert predict(fresh, f)["loss_pct"] == pytest.approx(predict(fresh, base(fresh, "Guayas"))["loss_pct"])


def test_register_canton(fresh):
    clim = load_climate()
    hist = clim[clim.area_name == "Los Rios"].drop(columns="area_name")
    register_area(fresh, "vinces", hist)
    f = fresh["scenario_features"]["vinces"]["normal"]
    r = predict(fresh, f)
    assert r["area_used"] == "vinces" and r["evidence"] == "indice_subnacional_no_validado"
    with pytest.raises(ValueError):
        register_area(fresh, "corto", hist.head(5))                    # sin historial suficiente


# ── Escenarios y lote ─────────────────────────────────────────────────────────────────
def test_analogs_follow_current_nino():
    clim = load_climate()
    strong = analog_years(clim, 4.5)
    assert 1998 in strong and all(y > 1961 for y in strong)
    assert analog_years(clim, -0.5) != strong                          # sin Niño: años neutros


@pytest.fixture(scope="module")
def batch(bundle):
    path = ARTIFACTS / f"loss_predictions_{VERSION}.parquet"
    if not path.exists():
        pytest.skip("sin predicciones: ml/.venv/bin/python -m ml.predict")
    return pd.read_parquet(path)


def test_batch_matches_loss_predictions_table(batch):
    for c in ("area_name", "crop_id", "scenario_id", "loss_pct", "loss_pct_low", "loss_pct_high",
              "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd", "risk_class",
              "top_factors"):
        assert c in batch.columns, c
    assert not batch[["area_name", "scenario_id"]].duplicated().any()
    assert set(batch.scenario_id) == set(SCENARIOS)
    assert batch.loss_pct.between(0, 100).all()
    assert (batch.loss_pct_low <= batch.loss_pct + 1e-9).all()
    assert (batch.loss_pct <= batch.loss_pct_high + 1e-9).all()
    assert set(batch.risk_class) <= {"bajo", "medio", "alto", "muy_alto"}
    assert np.allclose(batch.loss_t, batch.exposed_ha * batch.expected_yield_t_ha * batch.loss_pct / 100, atol=0.1)
    f = json.loads(batch.top_factors.iloc[0])
    assert {"feature", "value", "contribution_pct"} == set(f[0])


def test_batch_scenarios_make_sense(batch):
    nat = batch[batch.area_name == "national"].set_index("scenario_id")
    assert nat.loss_pct["nino_extremo"] > 30 > nat.loss_pct["normal"]
    assert nat.loss_pct["actual"] > nat.loss_pct["normal"]
    assert (batch[batch.area_name != "national"].evidence == "indice_subnacional_no_validado").all()
    assert "Sucumbios" not in set(batch.area_name)


def test_model_version_row():
    path = ARTIFACTS / f"model_version_{VERSION}.json"
    if not path.exists():
        pytest.skip("sin predicciones")
    row = json.loads(path.read_text())
    assert row["is_active"] and row["cv_scheme"] == "leave_one_year_out"
    for k in ("mae", "mae_baseline", "skill_vs_baseline", "interval_coverage_p10_p90", "nino_years_hit", "best"):
        assert k in row["metrics"], k
    assert row["metrics"]["nino_years_hit"]["1983"] and row["metrics"]["nino_years_hit"]["1998"]
