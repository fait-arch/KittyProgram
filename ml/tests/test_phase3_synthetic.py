"""Fase 3: el pipeline recupera la verdad conocida en datos sintéticos.

Modelos de referencia simples (Ridge y GBR cuantílico): si ELLOS recuperan la verdad,
el generador + target + validación funcionan, y la Fase 4 puede enchufar el modelo real
con la misma batería (`run_battery`).
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.dataset import FEATURES, TARGET, add_target, area_anomalies
from ml.synthetic import Truth, make_panel, stress_scenarios
from ml.validation import NinoBaseline, loyo, metrics

AREAS = ["national", "Los Rios", "Guayas", "Manabi"]
LIN_FEATS = ["fav_days_phytophthora", "saturated_days", "nino12_jan_jun", "solar_mean",
             "rh_mean", "t_mean", "wet_days"]                       # 4 reales + 3 distractores
NL_FEATS = ["rain_anom_pct", "fav_days_phytophthora", "saturated_days", "nino12_jan_jun",
            "solar_mean", "rh_mean"]


class QuantileGBR:
    """GBR con p10/p50/p90 (como el plan de la Fase 4, versión pequeña)."""

    def __init__(self, n=100):
        kw = dict(max_depth=2, n_estimators=n, learning_rate=0.05, subsample=0.8, random_state=0)
        self.m = {q: GradientBoostingRegressor(loss="quantile", alpha=q, **kw) for q in (0.1, 0.5, 0.9)}

    def fit(self, X, y):
        for m in self.m.values():
            m.fit(X, y)
        return self

    def predict(self, X):
        return self.m[0.5].predict(X)

    def predict_quantiles(self, X):
        return tuple(self.m[q].predict(X) for q in (0.1, 0.5, 0.9))


def ridge():
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0))


def run_battery(panel, make_model, feats):
    cv = loyo(panel, make_model, feats)
    base = loyo(panel, NinoBaseline, ["rain_anom_pct"])
    return cv, metrics(cv, base)


@pytest.fixture(scope="module")
def linear_panel():
    return add_target(make_panel(Truth.linear(), areas=AREAS, seed=1))


@pytest.fixture(scope="module")
def nonlinear_panel():
    return add_target(make_panel(Truth(), areas=AREAS, seed=2, extreme_years=5))


# ── Generador ─────────────────────────────────────────────────────────────────────────
def test_generator_schema_and_reproducible():
    a = make_panel(seed=7, areas=AREAS)
    b = make_panel(seed=7, areas=AREAS)
    pd.testing.assert_frame_equal(a, b)
    assert set(FEATURES) - {"y_anom_prev"} <= set(a.columns)
    assert len(a) == 65 * len(AREAS) and (a.yield_t_ha > 0).all()


def test_target_reconstructs_truth(linear_panel):
    """El detrending recupera la anomalía verdadera (la tendencia tecnológica no la contamina)."""
    assert linear_panel[TARGET].corr(linear_panel.y_true) > 0.9


def test_stress_scenarios_shape():
    s = stress_scenarios(make_panel(seed=3, areas=AREAS))
    assert list(s.scenario) == ["normal", "nino_extremo", "sequia"]
    assert s.set_index("scenario").loc["nino_extremo", "rain_anom_pct"] > 100


# ── Recuperación de la verdad ─────────────────────────────────────────────────────────
def test_recovers_linear_truth():
    """El pipeline (target sin tendencia + regresión sobre anomalías de área) recupera la verdad.

    Las features de humedad están muy correlacionadas entre sí (r ≈ 0.8), así que cada β
    individual tiene varianza alta en UNA muestra; se comprueba (1) que el efecto total
    f(x) se recupera casi perfecto y (2) que los β son insesgados en promedio de 10 semillas.
    """
    coefs, r = [], []
    for seed in range(1, 11):
        df = add_target(make_panel(Truth.linear(), areas=AREAS, seed=seed)).dropna(subset=[TARGET])
        X = area_anomalies(df, LIN_FEATS)
        X = X / X.std()
        m = LinearRegression().fit(X, df[TARGET])
        coefs.append(dict(zip(LIN_FEATS, m.coef_)))
        r.append(np.corrcoef(m.predict(X), df.f_true)[0, 1])
    c = pd.DataFrame(coefs).mean()
    assert min(r) > 0.9                                               # efecto total
    for k in ("fav_days_phytophthora", "saturated_days", "nino12_jan_jun"):
        assert c[k] == pytest.approx(Truth().beta[k], abs=0.8), k     # insesgado
    assert c["solar_mean"] > 0                                        # signo
    assert abs(c["t_mean"]) < 0.8                                     # distractor


def test_linear_skill_and_coverage(linear_panel):
    cv, m = run_battery(linear_panel, QuantileGBR, LIN_FEATS)
    assert m["skill"] > 0.15
    assert 0.65 <= m["coverage_80"] <= 0.93                           # p10–p90 ≈ 80 %


def test_nonlinear_extremes_detected(nonlinear_panel):
    cv_gbr, m_gbr = run_battery(nonlinear_panel, QuantileGBR, NL_FEATS)
    cv_lin, m_lin = run_battery(nonlinear_panel, ridge, NL_FEATS)
    assert m_gbr["skill"] > 0.1
    assert m_gbr["hit_rate_big_loss"] > 0.5                          # detecta los desplomes
    wet = cv_gbr.merge(nonlinear_panel[["area_name", "year", "rain_anom_pct"]]).rain_anom_pct > 100
    assert cv_gbr.pred[wet].mean() < -15                             # años extremos → pérdida grande


# ── Guardas contra fugas de información ───────────────────────────────────────────────
def test_null_truth_has_no_skill():
    """Si el clima no influye, la validación NO debe mostrar skill (si lo hace, hay fuga)."""
    panel = add_target(make_panel(Truth.null(), areas=AREAS, seed=5))
    cv = loyo(panel, ridge, NL_FEATS)
    assert abs(cv.y_cv.corr(cv.pred)) < 0.2
    assert metrics(cv)["mae"] > 0.9 * (cv.y_cv - cv.y_cv.mean()).abs().mean()


def test_shuffled_target_has_no_skill(linear_panel):
    rng = np.random.default_rng(0)
    p = linear_panel.copy()
    years = p.year.unique()
    perm = dict(zip(years, rng.permutation(years)))                  # baraja años completos
    p["yield_t_ha"] = p.set_index(["area_name", "year"]).yield_t_ha.reindex(
        list(zip(p.area_name, p.year.map(perm)))).to_numpy() * \
        (p.yield_true_trend / p.set_index(["area_name", "year"]).yield_true_trend.reindex(
            list(zip(p.area_name, p.year.map(perm)))).to_numpy())
    cv = loyo(p, ridge, LIN_FEATS)
    assert abs(cv.y_cv.corr(cv.pred)) < 0.2


def test_loyo_target_excludes_test_year(nonlinear_panel):
    """El target de test se calcula con una tendencia que no vio ese año."""
    cv = loyo(nonlinear_panel, ridge, NL_FEATS, years=[1990])
    ref = add_target(nonlinear_panel[["area_name", "year", "yield_t_ha"]], exclude={1990})
    exp = ref[ref.year == 1990].set_index("area_name")[TARGET]
    assert np.allclose(cv.set_index("area_name").y_cv.loc[exp.index], exp)


def test_area_anomalies_remove_level():
    df = pd.DataFrame({"area_name": ["a", "a", "b", "b"], "x": [1.0, 3.0, 10.0, 14.0]})
    assert area_anomalies(df, ["x"]).x.tolist() == [-1, 1, -2, 2]
    ref = pd.DataFrame({"area_name": ["a", "b"], "x": [0.0, 0.0]})
    assert area_anomalies(df, ["x"], ref=ref).x.tolist() == [1, 3, 10, 14]   # medias guardadas
