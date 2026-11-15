"""Datos sintéticos con VERDAD CONOCIDA para probar el modelo (Fase 3).

Idea: generamos un panel con la misma forma que `training_panel.parquet`, pero donde
sabemos exactamente cómo el clima afecta al rendimiento. Si el pipeline (target +
modelo + validación) no recupera esa verdad, está roto, y lo sabemos antes de
confiar en él con datos reales.

Modelo generador, para cada área a y año t:

    f(x)   = Σ_k β_k · z(x_k)  −  γ · max(0, rain_anom_pct − umbral)      (verdad)
    y*     = f(x) + α_a + u_t                                              (anomalía %)
    u_t    = ρ · u_{t−1} + ε_t,   ε_t ~ N(0, σ²)                           (ruido AR(1))
    T_t    = exp(a + b·t + c / (1 + e^{−(t−2009)/2}))                      (tendencia, salto CCN-51)
    R_t    = T_t · (1 + y*/100)                                            (rendimiento observado)

Las features se remuestrean por AÑO COMPLETO desde el panel real (si existe), así se
conservan las correlaciones entre variables y la coherencia entre áreas del mismo año.

    ml/.venv/bin/python -m ml.synthetic        # escribe data/processed/synthetic_panel.parquet
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import DATA_PROCESSED
from .dataset import FEATURES, area_anomalies

CLIMATE_COLS = [f for f in FEATURES if f != "y_anom_prev"]   # incluye ENSO_FEATURES


@dataclass
class Truth:
    """Parámetros verdaderos del generador."""
    beta: dict = field(default_factory=lambda: {
        "fav_days_phytophthora": -4.0,   # puntos % por desviación estándar
        "saturated_days": -3.0,
        "nino12_jan_jun": -2.0,
        "solar_mean": 1.5,
    })
    gamma: float = 0.4                   # puntos % por cada punto de anomalía de lluvia sobre el umbral
    threshold: float = 60.0              # % de anomalía de lluvia desde el que hay daño extra
    sigma: float = 5.0                   # ruido (puntos %)
    rho: float = 0.3                     # persistencia del ruido entre años
    area_sd: float = 2.0                 # efecto fijo de área

    @classmethod
    def linear(cls, **kw):
        return cls(gamma=0.0, **kw)

    @classmethod
    def null(cls, **kw):
        """Sin señal: el clima NO afecta al rendimiento. Un modelo honesto no debe tener skill."""
        return cls(beta={}, gamma=0.0, **kw)


def _feature_pool(rng: np.random.Generator) -> pd.DataFrame:
    """Features reales por año (todas las áreas); si no hay panel real, distribuciones paramétricas."""
    path = DATA_PROCESSED / "training_panel.parquet"
    if path.exists():
        p = pd.read_parquet(path)
        return p[["area_name", "year"] + CLIMATE_COLS].dropna()
    # Respaldo sin datos (CI): normales independientes con escalas parecidas a las reales
    years = np.arange(1961, 2026)
    areas = ["national", "Los Rios", "Guayas", "Manabi"]
    rows = []
    for y in years:
        shock = rng.gamma(0.5, 40) if rng.random() < 0.08 else rng.normal(0, 25)   # años Niño raros
        for a in areas:
            r = {c: rng.normal(0, 1) for c in CLIMATE_COLS}
            r.update(area_name=a, year=y, rain_anom_pct=shock + rng.normal(0, 10),
                     fav_days_phytophthora=30 + 0.3 * shock + rng.normal(0, 8),
                     saturated_days=20 + 0.3 * shock + rng.normal(0, 6))
            rows.append(r)
    return pd.DataFrame(rows)


def make_panel(truth: Truth | None = None, n_years: int = 65, start_year: int = 1961,
               areas: list[str] | None = None, seed: int = 0, extreme_years: int | None = None
               ) -> pd.DataFrame:
    """Panel sintético. Columnas = las del panel real + `y_true` (anomalía verdadera) y `f_true`.

    extreme_years: fuerza ese número de años con lluvia extrema (anomalía > umbral) para que
    la parte no lineal sea aprendible; por defecto se usa lo que traiga el remuestreo.
    """
    truth = truth or Truth()
    rng = np.random.default_rng(seed)
    pool = _feature_pool(rng)
    areas = areas or sorted(pool.area_name.unique())
    pool = pool[pool.area_name.isin(areas)]
    pool_years = sorted(pool.year.unique())

    years = np.arange(start_year, start_year + n_years)
    src = rng.choice(pool_years, size=n_years, replace=True)
    if extreme_years:
        wet = pool.groupby("year").rain_anom_pct.max()
        wet_years = wet[wet > truth.threshold + 20].index.to_numpy()
        if len(wet_years):
            idx = rng.choice(n_years, size=extreme_years, replace=False)
            src[idx] = rng.choice(wet_years, size=extreme_years, replace=True)

    rows = []
    for y, s in zip(years, src):
        block = pool[pool.year == s]
        for a in areas:
            r = block[block.area_name == a]
            if r.empty:                              # el área no existía ese año real: otra área
                r = block.sample(1, random_state=int(rng.integers(1e9)))
            rows.append(r.iloc[0][CLIMATE_COLS].to_dict() | {"area_name": a, "year": int(y)})
    df = pd.DataFrame(rows)

    # ENSO coherente con la lluvia (para no tener features contradictorias)
    df["nino12_jan_jun"] = 0.02 * df.rain_anom_pct + rng.normal(0, 0.4, len(df))

    # Verdad, definida sobre la anomalía DENTRO de cada área (lo único identificable: la
    # diferencia de nivel entre áreas la absorbe la tendencia de rendimiento de cada área)
    anom = area_anomalies(df, CLIMATE_COLS)
    z = anom / anom.std().replace(0, 1)
    f = sum(b * z[k] for k, b in truth.beta.items()) if truth.beta else pd.Series(0.0, index=df.index)
    f = f - truth.gamma * (df.rain_anom_pct - truth.threshold).clip(lower=0)
    df["f_true"] = f

    alpha = dict(zip(areas, rng.normal(0, truth.area_sd, len(areas))))
    eps = rng.normal(0, truth.sigma, (len(areas), n_years))
    u = np.zeros_like(eps)
    for t in range(n_years):
        u[:, t] = (truth.rho * u[:, t - 1] if t else 0) + eps[:, t]
    noise = {(a, y): u[i, t] for i, a in enumerate(areas) for t, y in enumerate(years)}
    df["y_true"] = df.f_true + df.area_name.map(alpha) + [noise[(a, y)] for a, y in zip(df.area_name, df.year)]
    df["y_true"] = df.y_true.clip(lower=-90)        # el rendimiento no puede ser negativo

    # Tendencia tecnológica + rendimiento observado
    base = dict(zip(areas, rng.uniform(np.log(0.2), np.log(0.4), len(areas))))
    tt = df.year - start_year
    trend = np.exp(df.area_name.map(base) + 0.004 * tt + 0.7 / (1 + np.exp(-(df.year - 2009) / 2)))
    df["yield_true_trend"] = trend
    df["yield_t_ha"] = trend * (1 + df.y_true / 100)
    df["level"] = np.where(df.area_name == "national", "national", "province")
    df["source"] = "synthetic"
    return df.sort_values(["area_name", "year"]).reset_index(drop=True)


def stress_scenarios(base: pd.DataFrame) -> pd.DataFrame:
    """Casos extremos para probar la API y el front: Niño costero extremo, sequía, normal."""
    med = base[CLIMATE_COLS].median()
    q = base[CLIMATE_COLS].quantile
    rows = {
        "normal": med,
        "nino_extremo": q(0.99).where(~med.index.isin(["solar_mean", "et0_total", "water_balance"]),
                                      q(0.01)),
        "sequia": q(0.01).where(~med.index.isin(["solar_mean", "et0_total"]), q(0.99)),
    }
    out = pd.DataFrame(rows).T
    out.loc["nino_extremo", "rain_anom_pct"] = 150.0
    out.loc["nino_extremo", "nino12_jan_jun"] = 3.0
    out.loc["sequia", "rain_anom_pct"] = -60.0
    return out.rename_axis("scenario").reset_index()


def main():
    df = make_panel(seed=42, extreme_years=4)
    df.to_parquet(DATA_PROCESSED / "synthetic_panel.parquet", index=False)
    print(f"{len(df)} filas · {df.area_name.nunique()} áreas · {df.year.min()}–{df.year.max()}")
    print(df.groupby(pd.cut(df.rain_anom_pct, [-100, -20, 20, 60, 500]), observed=True)
          .y_true.agg(["mean", "count"]).round(1))


if __name__ == "__main__":
    main()
