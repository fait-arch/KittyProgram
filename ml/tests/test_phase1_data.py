"""Validaciones de la Fase 1: los datos procesados existen y son físicamente razonables."""
import pandas as pd
import pytest

from ml.config import DATA_PROCESSED, PROVINCES

P = DATA_PROCESSED
pytestmark = pytest.mark.skipif(not (P / "climate_daily.parquet").exists(), reason="corre el ETL primero")


def test_enso():
    y = pd.read_parquet(P / "enso_yearly.parquet").set_index("year")
    assert y.index.min() <= 1950
    for yr in (1983, 1998, 2016):
        assert y.loc[yr, "enso_class"] == "nino"


def test_production():
    d = pd.read_parquet(P / "production.parquet")
    nat = d[(d.level == "national") & (d.source == "faostat")]
    assert nat.year.min() == 1961 and len(nat) >= 60
    prov = d[d.level == "province"]
    assert set(PROVINCES) <= set(prov.area_name)
    assert d.yield_t_ha.dropna().between(0.01, 3).all()
    # señal El Niño: caída nacional fuerte en 1983 y 1998
    s = nat.set_index("year").yield_t_ha
    assert s[1983] < 0.7 * s[1982] and s[1998] < 0.7 * s[1997]


def test_climate():
    c = pd.read_parquet(P / "climate_daily.parquet")
    assert set(PROVINCES) | {"national"} <= set(c.area_name)
    assert c.date.min() <= pd.Timestamp("1961-01-01")
    assert not c.duplicated(["date", "area_name"]).any()
    assert c.t2m_c.between(5, 40).all()
    assert c.rh_pct.dropna().between(5, 101).all()
    lr = c[c.area_name == "Los Rios"].set_index("date")
    gpm = lr.precip_gpm_mm.resample("YE").sum()
    assert gpm["1998"].iloc[0] > 1.5 * gpm["2000":"2014"].median()   # Niño 1998
