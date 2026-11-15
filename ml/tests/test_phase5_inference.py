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
            known = set(bundle["model"].model.pre_.mean_.index)     # nombre o uuid con normal climática
            assert required <= set(v) and v["_area"] in known and v["_sens"]


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


# ── Probabilidad de año malo y cantones ──────────────────────────────────────────────
def test_prob_loss_gt20_is_consistent(bundle):
    f0 = base(bundle, "national", "normal")
    r0 = predict(bundle, f0)
    r1 = predict(bundle, base(bundle, "national", "nino_extremo"))
    assert 0 <= r0["prob_loss_gt20"] <= 1 and 0 <= r1["prob_loss_gt20"] <= 1
    assert r1["prob_loss_gt20"] > 0.8 > r0["prob_loss_gt20"]
    probs = [predict(bundle, adjust_features(f0, {"rain_delta_pct": d}, {}))["prob_loss_gt20"]
             for d in (0, 40, 80, 120)]
    assert np.all(np.diff(probs) >= -1e-9)                            # más lluvia, más riesgo


def test_batch_has_probability(batch):
    assert batch.prob_loss_gt20.between(0, 1).all()
    nat = batch[batch.area_name == "national"].set_index("scenario_id")
    assert nat.prob_loss_gt20["nino_extremo"] > 0.8


@pytest.fixture(scope="module")
def areas_batch():
    path = ARTIFACTS / f"loss_predictions_areas_{VERSION}.parquet"
    if not path.exists():
        pytest.skip("sin predicciones por cantón: ml/.venv/bin/python -m ml.cantons_predict")
    return pd.read_parquet(path)


def test_canton_predictions(areas_batch):
    c = areas_batch[(areas_batch.kind == "canton") & ~areas_batch.scenario_id.str.endswith("_2050")]
    assert c.area_id.nunique() >= 100                                  # ~125 de 126 cantones
    assert c.area_id.str.match(r"^[0-9a-f-]{36}$").all()                # uuid de Supabase
    assert c.loss_pct.between(0, 100).all() and c.prob_loss_gt20.between(0, 1).all()
    assert (c.evidence == "indice_subnacional_no_validado").all()
    assert not c[["area_id", "scenario_id"]].duplicated().any()
    assert set(areas_batch.kind) == {"country", "province", "canton"}
    ext = c[c.scenario_id == "nino_extremo"].loss_pct.mean()
    nor = c[c.scenario_id == "normal"].loss_pct.mean()
    assert ext > nor + 15


def test_bundle_knows_cantons(bundle, areas_batch):
    cid = areas_batch[areas_batch.kind == "canton"].area_id.iloc[0]
    if cid not in bundle["scenario_features"]:
        pytest.skip("bundle sin cantones (regenerar con ml.cantons_predict)")
    r = predict(bundle, bundle["scenario_features"][cid]["normal"])
    assert r["area_used"] == cid and 0 <= r["loss_pct"] <= 100


# ── Proyecciones 2026–2050 ───────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def projections():
    path = ARTIFACTS / f"projections_{VERSION}.parquet"
    if not path.exists():
        pytest.skip("sin proyecciones: ml/.venv/bin/python -m ml.projections")
    return pd.read_parquet(path)


def test_projection_trajectory(projections):
    p = projections
    assert set(p.ssp) == {"ssp245", "ssp585"} and set(p.base) == {"tipico", "nino_extremo"}
    for _, g in p.groupby(["area_id", "ssp", "base"]):
        assert sorted(g.year) == list(range(2026, 2051))               # todos los años hasta 2050
    assert p.loss_pct.between(0, 100).all()
    assert (p.loss_pct_min <= p.loss_pct + 1e-6).all() and (p.loss_pct <= p.loss_pct_max + 1e-6).all()
    nat = p[(p.area_name == "national") & (p.year == 2050)]
    assert nat[nat.base == "nino_extremo"].loss_pct.min() > 3 * nat[nat.base == "tipico"].loss_pct.max()
    assert (nat.anual_frecuencia_x2 >= nat.anual_frecuencia_hoy - 1e-9).all()   # más Niños extremos → más riesgo
    dt = nat[nat.base == "tipico"].set_index("ssp").dT_ene_jun
    assert dt["ssp585"] > dt["ssp245"] > 0


def test_2050_scenarios_in_area_predictions(areas_batch):
    s = areas_batch[areas_batch.scenario_id.isin(["ssp245_2050", "ssp585_2050"])]
    if s.empty:
        pytest.skip("escenarios 2050 sin integrar (ml.projections)")
    n_areas = areas_batch[areas_batch.scenario_id == "normal"].area_id.nunique()
    assert s.groupby("scenario_id").area_id.nunique().eq(n_areas).all()
    assert (s.evidence == "proyeccion_cmip6_no_validada").all()
    assert s.loss_pct.between(0, 100).all()


# ── Aptitud FAO GAEZ y matriz de decisión ────────────────────────────────────────────
def test_zones_matrix():
    path = ARTIFACTS / f"zones_{VERSION}.parquet"
    if not path.exists():
        pytest.skip("sin matriz de zonas: ml/.venv/bin/python -m ml.zones")
    z = pd.read_parquet(path)
    from ml.zones import RISK_MAX, SUIT_MIN, zone
    assert set(z.zone_2050.dropna()) <= {"segura", "manejo", "transicion", "critica"}
    assert z.si_2050_rcp85_alto.dropna().between(0, 10000).all()
    assert (z.kind == "canton").sum() >= 100 and z.zone_2050.notna().mean() > 0.95
    for r in z.dropna(subset=["zone_2050"]).itertuples():
        assert r.zone_2050 == zone(r.si_2050_rcp85_alto, r.loss_pct_nino_extremo)
    assert zone(SUIT_MIN + 1, RISK_MAX + 1) == "manejo" and zone(SUIT_MIN - 1, RISK_MAX - 1) == "transicion"


# ── VIIRS (respaldo de MODIS) y monitor SMAP ─────────────────────────────────────────
def test_viirs_calibration():
    import pandas as pd
    from ml.features import fit_evi_calibration
    rng = np.random.default_rng(0)
    dates = pd.date_range("2015-01-01", "2020-06-30", freq="16D")
    v = rng.uniform(0.3, 0.5, len(dates))
    d = pd.DataFrame({"date": dates, "area_name": "x", "viirs_evi": v, "modis_evi": (0.05 + 0.9 * v) * 1e4})
    a, b = fit_evi_calibration(d)["x"]
    assert a == pytest.approx(0.05, abs=1e-6) and b == pytest.approx(0.9, abs=1e-6)


def test_soil_monitor():
    path = ARTIFACTS / "monitor_soil_v1.parquet"
    if not path.exists():
        pytest.skip("sin monitor: ml/.venv/bin/python -m ml.monitor")
    m = pd.read_parquet(path)
    assert set(m.estado.dropna()) <= {"seco", "normal", "humedo", "encharcado"}
    assert (m.kind == "canton").groupby(m.area_id).any().sum() >= 100
    assert m.sm_m3m3.between(0, 1).all() and m.dias_saturados_pct.between(0, 100).all()
    assert m.ultimo_dato.max().year >= 2026
