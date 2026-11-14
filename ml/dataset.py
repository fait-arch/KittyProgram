"""Panel de entrenamiento área × año: target + features climáticas + ENSO.

    ml/.venv/bin/python -m ml.dataset      # escribe data/processed/training_panel.parquet

Target (docs/05-modelo-predictivo.md):
    y = 100 · (R − T) / T
R = rendimiento (t/ha); T = tendencia del área estimada SIN el propio año (LOWESS sobre
log-rendimiento, dejando un año fuera). pérdida % = max(0, −y).
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess

from .config import ARTIFACTS, DATA_PROCESSED, PROVINCES
from .features import CLIMATE_FEATURES, BiasCorrection, build_features

ENSO_FEATURES = ["oni_jan_jun", "nino12_jan_jun", "nino34_jan_jun", "oni_djf", "nino12_prev_ond"]
LAG_FEATURES = ["y_anom_prev"]
FEATURES = CLIMATE_FEATURES + ENSO_FEATURES + LAG_FEATURES
TARGET = "y_anom_pct"

# Ancho de la ventana LOWESS en AÑOS (se convierte a fracción según la longitud de la serie)
TREND_SPAN_YEARS = 15


def loo_trend(years: np.ndarray, yields: np.ndarray, exclude: set[int] | None = None) -> np.ndarray:
    """Tendencia de rendimiento en cada año, ajustada sin ese año (leave-one-out).

    `exclude`: años adicionales que NO pueden usarse para ajustar la tendencia (p. ej. el año
    de test en validación cruzada, para un target sin fuga de información).
    LOWESS local-lineal sobre log(rendimiento): robusto a años atípicos (it=2) y a tendencias
    no lineales (salto de CCN-51 desde 2009).
    """
    years = np.asarray(years, float)
    logy = np.log(np.asarray(yields, float))
    exclude = exclude or set()
    out = np.full(len(years), np.nan)
    for i, y in enumerate(years):
        keep = np.array([(j != i) and (int(yy) not in exclude) for j, yy in enumerate(years)])
        if keep.sum() < 5:
            continue
        frac = min(1.0, max(TREND_SPAN_YEARS / keep.sum(), 6 / keep.sum()))
        fit = lowess(logy[keep], years[keep], frac=frac, it=2, xvals=np.array([y]))
        out[i] = fit[0]
        if np.isnan(out[i]):                       # extremo sin vecinos suficientes: recta
            b, a = np.polyfit(years[keep], logy[keep], 1)
            out[i] = a + b * y
    return np.exp(out)


def add_target(prod: pd.DataFrame, exclude: set[int] | None = None) -> pd.DataFrame:
    """Añade yield_trend, y_anom_pct, loss_pct e y_anom_prev por área."""
    out = []
    for _, g in prod.groupby("area_name"):
        g = g.sort_values("year").copy()
        g["yield_trend"] = loo_trend(g.year.to_numpy(), g.yield_t_ha.to_numpy(), exclude)
        g[TARGET] = 100 * (g.yield_t_ha - g.yield_trend) / g.yield_trend
        g["loss_pct"] = (-g[TARGET]).clip(lower=0)
        prev = g.set_index("year")[TARGET]
        g["y_anom_prev"] = (g.year - 1).map(prev).to_numpy()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def load_production() -> pd.DataFrame:
    """Serie de rendimiento por área: nacional (FAOSTAT 1961– + ESPAC último año) y 7 provincias."""
    p = pd.read_parquet(DATA_PROCESSED / "production.parquet")
    p = p[~p.suppressed & p.yield_t_ha.notna() & (p.yield_t_ha > 0)]
    nat = p[p.level == "national"].sort_values("source")           # espac < faostat
    nat = nat.drop_duplicates("year", keep="last").assign(area_name="national")  # prioriza FAOSTAT
    prov = p[(p.level == "province") & p.area_name.isin(PROVINCES)]
    cols = ["area_name", "level", "year", "harvested_ha", "production_t", "yield_t_ha", "source"]
    return pd.concat([nat, prov])[cols].sort_values(["area_name", "year"]).reset_index(drop=True)


def load_enso() -> pd.DataFrame:
    y = pd.read_parquet(DATA_PROCESSED / "enso_yearly.parquet")
    m = pd.read_parquet(DATA_PROCESSED / "enso_monthly.parquet")
    ond = (m[m.month_date.dt.month >= 10].groupby(m.month_date.dt.year).nino12_anom.mean()
           .rename("nino12_prev_ond"))
    ond.index = ond.index + 1                                       # oct–dic del año anterior
    y = y.merge(ond, left_on="year", right_index=True, how="left")
    return y[["year", "oni_jan_jun", "nino12_jan_jun", "nino34_jan_jun", "oni_djf",
              "nino12_prev_ond", "enso_class", "nino_strength"]]


def fit_bias_correction() -> tuple[BiasCorrection, pd.DataFrame]:
    daily = pd.read_parquet(DATA_PROCESSED / "climate_daily.parquet")
    bc = BiasCorrection.fit(daily, pd.read_parquet(DATA_PROCESSED / "worldclim_monthly.parquet"),
                            pd.read_parquet(DATA_PROCESSED / "area_meta.parquet"))
    return bc, daily


def build_panel(exclude: set[int] | None = None) -> pd.DataFrame:
    bc, daily = fit_bias_correction()
    feats = build_features(daily, bc)
    panel = (add_target(load_production(), exclude)
             .merge(feats, on=["area_name", "year"], how="left")
             .merge(load_enso(), on="year", how="left"))
    panel["is_nino"] = (panel.enso_class == "nino").astype(int)
    return panel.sort_values(["area_name", "year"]).reset_index(drop=True)


def main():
    bc, daily = fit_bias_correction()
    feats = build_features(daily, bc)
    feats.to_parquet(DATA_PROCESSED / "features_area_year.parquet", index=False)
    joblib.dump(bc, ARTIFACTS / "bias_correction.joblib")
    panel = build_panel()
    panel.to_parquet(DATA_PROCESSED / "training_panel.parquet", index=False)
    panel.to_csv(DATA_PROCESSED / "training_panel.csv", index=False)

    ok = panel.dropna(subset=[TARGET])
    print(f"Panel: {len(panel)} filas · {len(ok)} con target · {ok.year.min()}–{ok.year.max()}")
    print(ok.groupby("area_name").agg(n=("year", "size"), desde=("year", "min"),
                                      hasta=("year", "max"), sd_anom=(TARGET, "std")).round(1))
    print("\nAnomalía media de rendimiento (%) por clase ENSO:")
    print(ok.groupby(["level", "enso_class"])[TARGET].agg(["mean", "median", "count"]).round(1))
    nat = ok[ok.area_name == "national"].set_index("year")
    print("\nNacional, años Niño fuertes:")
    print(nat.loc[[1983, 1987, 1992, 1998, 2016, 2024],
                  ["yield_t_ha", "yield_trend", TARGET, "rain_anom_pct", "nino12_jan_jun"]].round(2))
    num = ok[FEATURES + [TARGET]].corr(method="spearman")[TARGET].drop(TARGET)
    print("\nCorrelación de Spearman con el target (todas las áreas):")
    print(num.sort_values().round(2).to_string())


if __name__ == "__main__":
    main()
