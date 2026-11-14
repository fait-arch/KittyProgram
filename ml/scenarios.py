"""Escenarios climáticos y sensibilidades para predecir (Fase 5).

Un escenario es el vector de features de la época lluviosa (ene–jun) de un área bajo cierta
condición. Mismos ids que la tabla `scenarios` de Supabase (migración 0005):

    normal        media de los años ENSO neutros 2001–2025
    nino          media de los años El Niño 2001–2025
    nina          media de los años La Niña 2001–2025
    nino_extremo  media de 1983 y 1998 (los dos Niños costeros extremos; no está en la BD)
    actual        temporada ene–jun que viene, por ANÁLOGOS: los años cuyo ago–oct previo tuvo
                  Niño 1+2 ≥ +2 °C (como ahora). Cada análogo se predice por separado y se
                  promedia: el vector guardado es la media, la pérdida es la media de pérdidas.

Sensibilidades (para los sliders del what-if), ajustadas por área con la serie 1961–2025:

    Δ saturated_days        = b_sat · Δ rain_total
    Δ fav_days_phytophthora = b_fav · Δ rain_total + c_fav · Δ t_mean
    Δ solar_mean            = b_sol · Δ rain_total
    Δ rain_total            = b_n12 · Δ nino12_jan_jun      (o b_oni · Δ oni_jan_jun)

Así el slider "lluvia +20 %" mueve también el suelo saturado y los días favorables, como en
un año real, en vez de cambiar una sola variable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_PROCESSED

KEY = ["area_name", "year"]
SCENARIO_PERIOD = (2001, 2025)                 # periodo de la tabla `scenarios`
EXTREME_YEARS = (1983, 1998)
ANALOG_ASO_MIN = 2.0                           # °C de Niño 1+2 en ago–oct para ser análogo
CONTEXT = ["nino12_jan_jun", "oni_jan_jun"]   # no entran al modelo; sirven para los sliders
SCENARIOS = ["normal", "nino", "nina", "nino_extremo", "actual"]
MAX_DAYS = 181                                 # días de ene–jun


def load_climate() -> pd.DataFrame:
    """Features climáticas área × año 1961–2025 con el ENSO del año (y el ago–oct previo)."""
    f = pd.read_parquet(DATA_PROCESSED / "features_area_year.parquet")
    y = pd.read_parquet(DATA_PROCESSED / "enso_yearly.parquet")[["year", "enso_class"] + CONTEXT]
    y = y.merge(aso_previous().rename("nino12_aso_prev"), left_on="year", right_index=True, how="left")
    return f.merge(y, on="year", how="left")


def aso_previous(monthly: pd.DataFrame | None = None) -> pd.Series:
    """Niño 1+2 medio de ago–oct del año anterior, indexado por el año de la temporada."""
    m = monthly if monthly is not None else pd.read_parquet(DATA_PROCESSED / "enso_monthly.parquet")
    m = m.dropna(subset=["nino12_anom"])
    s = m[m.month_date.dt.month.isin([8, 9, 10])].groupby(m.month_date.dt.year).nino12_anom.mean()
    s.index = s.index + 1
    return s


def current_aso(monthly: pd.DataFrame | None = None) -> tuple[int, float]:
    """(año de la próxima temporada, Niño 1+2 ago–oct más reciente)."""
    s = aso_previous(monthly)
    return int(s.index.max()), float(s.iloc[-1])


def analog_years(climate: pd.DataFrame, aso_now: float, min_aso: float = ANALOG_ASO_MIN) -> list[int]:
    """Años históricos con Niño 1+2 de ago–oct previo ≥ min(aso_now, umbral)."""
    thr = min(aso_now, min_aso) if aso_now >= 0.5 else None
    nat = climate[climate.area_name == "national"].dropna(subset=["nino12_aso_prev"])
    if thr is None:                                             # sin Niño: análogos = neutros
        return sorted(nat[nat.enso_class == "neutral"].year.unique().tolist())
    return sorted(nat[nat.nino12_aso_prev >= thr].year.unique().tolist())


def scenario_years(climate: pd.DataFrame, aso_now: float | None = None) -> dict[str, list[int]]:
    a, b = SCENARIO_PERIOD
    nat = climate[(climate.area_name == "national") & climate.year.between(a, b)]
    out = {c: sorted(nat[nat.enso_class == k].year.tolist())
           for c, k in (("normal", "neutral"), ("nino", "nino"), ("nina", "nina"))}
    out["nino_extremo"] = list(EXTREME_YEARS)
    if aso_now is None:
        aso_now = current_aso()[1]
    out["actual"] = analog_years(climate, aso_now)
    return out


def scenario_features(climate: pd.DataFrame, features: list[str], years: dict[str, list[int]]
                      ) -> dict[str, dict[str, dict]]:
    """{area_name: {scenario: {feature: media}}} con las features del modelo + contexto ENSO."""
    cols = list(dict.fromkeys(features + CONTEXT))
    out: dict[str, dict[str, dict]] = {}
    for area, g in climate.groupby("area_name"):
        out[area] = {}
        for sc, yrs in years.items():
            sel = g[g.year.isin(yrs)]
            if sel.empty:
                continue
            v = sel[cols].mean().round(4).to_dict()
            v["_area"], v["_years"] = area, [int(y) for y in sel.year]
            out[area][sc] = v
    return out


# ── Sensibilidades ────────────────────────────────────────────────────────────────────
def _slope(y: pd.Series, X: pd.DataFrame) -> np.ndarray:
    d = pd.concat([y, X], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d.iloc[:, 1:].to_numpy(float)])
    return np.linalg.lstsq(A, d.iloc[:, 0].to_numpy(float), rcond=None)[0][1:]


def fit_sensitivities(climate: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Pendientes por área (MCO sobre 1961–2025). Ver el docstring del módulo."""
    out = {}
    for area, g in climate.groupby("area_name"):
        if g.rain_total.notna().sum() < 10:
            continue
        r = g[["rain_total"]]
        b_fav, c_fav = _slope(g.fav_days_phytophthora, g[["rain_total", "t_mean"]])
        out[area] = {
            "sat_per_mm": float(_slope(g.saturated_days, r)[0]),
            "fav_per_mm": float(b_fav), "fav_per_c": float(c_fav),
            "sol_per_mm": float(_slope(g.solar_mean, r)[0]),
            "mm_per_nino12": float(_slope(g.rain_total, g[["nino12_jan_jun"]])[0]),
            "mm_per_oni": float(_slope(g.rain_total, g[["oni_jan_jun"]])[0]),
        }
    return out
