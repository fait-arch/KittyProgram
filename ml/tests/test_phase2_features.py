"""Validaciones de la Fase 2: fórmulas, corrección de sesgo, target y panel."""
import numpy as np
import pandas as pd
import pytest

from ml import features as F
from ml.config import DATA_PROCESSED as P
from ml.dataset import FEATURES, TARGET, add_target, build_panel, fit_bias_correction, loo_trend

needs_data = pytest.mark.skipif(not (P / "climate_daily.parquet").exists(), reason="corre el ETL primero")


# ── Fórmulas ──────────────────────────────────────────────────────────────────────────
def test_relative_humidity():
    assert F.relative_humidity(25, 25) == pytest.approx(100)
    assert F.relative_humidity(30, 20) == pytest.approx(55.1, abs=0.5)      # tabla psicrométrica


def test_et0_fao56_example_18():
    """FAO-56, ejemplo 18 (Bruselas, 6 de julio): ET0 = 3.9 mm/día."""
    td = 12.07                                   # ea = 1.409 kPa
    u10 = 2.078 / (4.87 / np.log(67.8 * 10 - 5.42))
    et0 = F.et0_penman_monteith(21.5, 12.3, td, 22.07, u10, 187, 50.8, 100)
    assert float(et0) == pytest.approx(3.9, abs=0.1)


def test_ecocrop_trapezoid():
    t = lambda x: float(F.trapezoid(x, 10, 21, 32, 38))
    assert t(5) == 0 and t(10) == 0 and t(38) == 0 and t(25) == 1
    assert t(15.5) == pytest.approx(0.5) and t(35) == pytest.approx(0.5)
    assert float(F.ecocrop_suitability(25, 2000)) == 1
    assert float(F.ecocrop_suitability(25, 1050)) == pytest.approx(0.5)     # limita la lluvia


def test_quantile_mapping_monotone_and_extrapolates():
    src, dst = np.linspace(0, 100, 1001), np.linspace(0, 25, 1001)
    x = np.array([0, 10, 50, 100, 200.0])
    y = F._qmap(x, src, dst)
    assert np.all(np.diff(y) > 0) and y[3] == pytest.approx(25) and y[4] == pytest.approx(50)


# ── Target ────────────────────────────────────────────────────────────────────────────
def test_trend_excludes_own_year():
    years = np.arange(1990, 2015)
    y = 0.3 + 0.01 * (years - 1990)
    base = loo_trend(years, y)
    shock = y.copy(); shock[10] *= 0.4                     # desplome en el año 2000
    after = loo_trend(years, shock)
    assert after[10] == pytest.approx(base[10], rel=1e-9)  # su tendencia no ve su propio valor
    assert base == pytest.approx(y, rel=0.02)              # recupera una tendencia lineal


def test_trend_exclude_extra_year():
    years = np.arange(1990, 2015); y = 0.3 + 0.01 * (years - 1990)
    shock = y.copy(); shock[10] *= 0.4
    t = loo_trend(years, shock, exclude={2000})
    assert t == pytest.approx(loo_trend(years, y, exclude={2000}), rel=1e-9)   # 2000 no influye en nadie


def test_target_signs():
    d = pd.DataFrame({"area_name": "x", "year": np.arange(1990, 2015),
                      "yield_t_ha": 0.3 + 0.01 * np.arange(25)})
    d.loc[10, "yield_t_ha"] *= 0.5
    r = add_target(d).set_index("year")
    assert r.loc[2000, TARGET] == pytest.approx(-50, abs=3) and r.loc[2000, "loss_pct"] > 45
    assert r.loc[2001, "y_anom_prev"] == pytest.approx(r.loc[2000, TARGET])


# ── Datos reales ──────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def real():
    bc, daily = fit_bias_correction()
    return bc, daily, build_panel()


@needs_data
def test_bias_correction_real(real):
    bc, daily, _ = real
    d = bc.apply(daily)
    wc = pd.read_parquet(P / "worldclim_monthly.parquet")
    for area, g in d[d.date.dt.year.between(1961, 1990)].groupby("area_name"):
        clim = g.groupby(g.date.dt.month).t2m_c.mean()
        ref = wc[wc.area_name == area].set_index("month").wc_tavg_c
        assert np.allclose(clim, ref, atol=0.01)           # temperatura = WorldClim en el periodo base
    ov = d.dropna(subset=["precip_gpm_mm"])
    tot = ov.groupby("area_name")[["precip_mm", "precip_gpm_mm"]].sum()
    assert ((tot.precip_mm / tot.precip_gpm_mm - 1).abs() < 0.03).all()   # sesgo de lluvia < 3 %
    assert (d.precip_mm >= 0).all()


@needs_data
def test_rain_matches_gpm_by_year(real):
    bc, daily, panel = real
    g = daily[daily.date.dt.month <= 6]
    gpm = (g.groupby(["area_name", g.date.dt.year]).precip_gpm_mm.sum(min_count=150)
           .rename("gpm").rename_axis(["area_name", "year"]).reset_index().dropna())
    feats = F.build_features(daily, bc).merge(gpm)
    r = feats.groupby("area_name").apply(lambda x: x.rain_total.corr(x.gpm), include_groups=False)
    from ml.config import PROVINCES
    coast = [a for a in PROVINCES if a != "Sucumbios"] + ["national"]
    assert r[coast].min() > 0.7                             # Costa; Amazonía y Sierra son más débiles


@needs_data
def test_panel(real):
    _, _, panel = real
    assert len(panel) >= 200 and panel.year.min() == 1961
    assert not panel.duplicated(["area_name", "year"]).any()
    climate = [f for f in FEATURES if f != "y_anom_prev"]
    # único hueco permitido: oct–dic de 1960 (ERA5 se extrajo desde 1961)
    assert panel.loc[panel.year > 1961, climate].isna().sum().sum() == 0
    assert panel[TARGET].between(-100, 300).all()
    assert panel.fav_days_monilia.between(0, 182).all() and panel.suitability.between(0, 1).all()
    nat = panel[panel.area_name == "national"].set_index("year")
    assert nat.loc[1983, TARGET] < -30 and nat.loc[1998, TARGET] < -30      # desplomes de El Niño
    lr = F.build_features(real[1], real[0]).query("area_name == 'Los Rios'").set_index("year")
    assert lr.loc[1998, "rain_anom_pct"] > 100 and lr.loc[1998, "heavy_rain_days"] > 3 * lr.heavy_rain_days.median()
