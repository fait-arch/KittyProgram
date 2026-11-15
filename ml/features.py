"""Features climáticas del modelo CacaoResiliente.

Las MISMAS funciones se usan para entrenar y para predecir (API): reciben el clima
diario de un área y devuelven una fila de features por área y año.

Flujo:
    daily (climate_daily.parquet)
      -> correct_bias()      temperatura (delta WorldClim) + lluvia (quantile mapping a GPM)
      -> add_daily_derived() HR, ET0 FAO-56, indicadores diarios de enfermedad
      -> yearly_features()   agregación por ventana de meses

Todas las correcciones se guardan en un objeto BiasCorrection serializable, para que la
API aplique exactamente lo mismo a datos nuevos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import ECOCROP_R, ECOCROP_T, RAINY_MONTHS

# ── Umbrales (referenciales de literatura; validar con INIAP) ──────────────────────────
RH_MONILIA = 85.0          # % HR media diaria; Leandro-Muñoz et al. 2017 (humedad -> infección)
T_MONILIA = (22.0, 30.0)   # °C; óptimo térmico ~30 °C para síntomas/esporulación
RH_PHYTO = 90.0            # % mazorca negra: aire casi saturado
RAIN_PHYTO = 10.0          # mm/día: salpique de esporas
T_PHYTO = (20.0, 30.0)
WET_DAY = 1.0              # mm/día (definición OMM de día lluvioso)
HEAVY_RAIN = 30.0          # mm/día sobre la MEDIA del área (≈ >50 mm puntual)
REF_PERIOD = (1991, 2020)  # normal climatológica OMM para percentiles

QM_QUANTILES = np.linspace(0, 1, 1001)


# ══════════════════════════════════════════════════════════════════════════════════════
# 1. Fórmulas físicas
# ══════════════════════════════════════════════════════════════════════════════════════
def sat_vapor_pressure(t_c):
    """Presión de vapor de saturación (kPa), FAO-56 ec. 11:  e°(T) = 0.6108·exp(17.27T/(T+237.3))."""
    return 0.6108 * np.exp(17.27 * np.asarray(t_c, float) / (np.asarray(t_c, float) + 237.3))


def relative_humidity(t_c, td_c):
    """HR (%) = 100·e°(Td)/e°(T). Acotada a [0, 100]."""
    return np.clip(100.0 * sat_vapor_pressure(td_c) / sat_vapor_pressure(t_c), 0, 100)


def et0_penman_monteith(tmax, tmin, td, rs, u10, doy, lat_deg, elev_m):
    """ET0 diaria (mm/día), FAO-56 Penman-Monteith (Allen et al. 1998, ec. 6):

        ET0 = [0.408·Δ·(Rn − G) + γ·900/(T+273)·u2·(es − ea)] / [Δ + γ·(1 + 0.34·u2)]

    tmax, tmin, td en °C; rs = radiación solar entrante (MJ/m²/día); u10 = viento a 10 m (m/s);
    doy = día del año; G ≈ 0 a escala diaria.
    """
    tmax, tmin, td, rs, u10, doy = (np.asarray(a, float) for a in (tmax, tmin, td, rs, u10, doy))
    t = (tmax + tmin) / 2
    p = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26                # ec. 7
    gamma = 0.000665 * p                                               # ec. 8
    delta = 4098 * sat_vapor_pressure(t) / (t + 237.3) ** 2            # ec. 13
    es = (sat_vapor_pressure(tmax) + sat_vapor_pressure(tmin)) / 2     # ec. 12
    ea = np.minimum(sat_vapor_pressure(td), es)                        # ec. 14
    u2 = u10 * 4.87 / np.log(67.8 * 10 - 5.42)                         # ec. 47

    # Radiación extraterrestre Ra (ec. 21–25)
    phi = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
    rso = (0.75 + 2e-5 * elev_m) * ra                                  # ec. 37
    rns = (1 - 0.23) * rs                                              # ec. 38
    sigma = 4.903e-9
    rel = np.clip(rs / rso, 0.25, 1.0)
    rnl = (sigma * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
           * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * rel - 0.35))        # ec. 39
    rn = rns - rnl
    et0 = (0.408 * delta * rn + gamma * 900 / (t + 273) * u2 * (es - ea)) / (
        delta + gamma * (1 + 0.34 * u2))
    return np.maximum(et0, 0)


def trapezoid(x, vmin, opmin, opmax, vmax):
    """Aptitud ECOCROP en [0, 1]: 0 fuera de [vmin, vmax], 1 en [opmin, opmax], lineal entre medias."""
    x = np.asarray(x, float)
    up = (x - vmin) / (opmin - vmin)
    down = (vmax - x) / (vmax - opmax)
    return np.clip(np.minimum(np.minimum(up, down), 1.0), 0.0, 1.0)


def ecocrop_suitability(t_mean_annual, rain_annual):
    """suit = min(S_T, S_R)  (factor limitante; Hijmans et al., dismo::ecocrop)."""
    return np.minimum(trapezoid(t_mean_annual, *ECOCROP_T), trapezoid(rain_annual, *ECOCROP_R))


# ══════════════════════════════════════════════════════════════════════════════════════
# 2. Corrección de sesgo
# ══════════════════════════════════════════════════════════════════════════════════════
def _season(month):
    """Ventana de ±1 mes para tener muestra suficiente en el quantile mapping."""
    return [(month - 2) % 12 + 1, month, month % 12 + 1]


@dataclass
class BiasCorrection:
    """Parámetros de corrección por área. Se ajusta una vez y se guarda con el modelo.

    temp_delta[area][var][mes]  -> °C a sumar a ERA5 (WorldClim − ERA5, 1961–1990)
    qm[area][mes]               -> (cuantiles ERA5, cuantiles GPM) para mapear lluvia
    thresholds[area][nombre]    -> percentiles de referencia (lluvia p95, suelo p90)
    meta[area]                  -> lat, elev_m
    rain_ref                    -> columna de lluvia de referencia del quantile mapping
                                   (precip_gpm_mm 1998→ o precip_chirps_mm 1981→)
    use_obs                     -> True: donde hay dato de `rain_ref` se usa tal cual y el
                                   quantile mapping de ERA5 solo rellena los años anteriores
    """
    temp_delta: dict = field(default_factory=dict)
    qm: dict = field(default_factory=dict)
    thresholds: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    rain_ref: str = "precip_gpm_mm"
    use_obs: bool = False

    # ---- ajuste -------------------------------------------------------------------
    @classmethod
    def fit(cls, daily: pd.DataFrame, worldclim: pd.DataFrame, area_meta: pd.DataFrame,
            qm_years: tuple[int, int] | None = None, rain_ref: str = "precip_gpm_mm",
            use_obs: bool = False, temp_delta: dict | None = None) -> "BiasCorrection":
        """temp_delta: {área: {var: {mes: °C}}} ya calculado (p. ej. cantones sin ERA5 1961–1990)."""
        bc = cls(rain_ref=rain_ref, use_obs=use_obs)
        daily = daily.assign(month=daily.date.dt.month, year=daily.date.dt.year)
        for area, g in daily.groupby("area_name"):
            m = area_meta.set_index("area_name").loc[area]
            bc.meta[area] = {"lat": float(m.lat), "elev_m": float(m.elev_m)}

            # Temperatura: delta mensual contra WorldClim v1 (mismo periodo 1961–1990)
            ref = g[g.year.between(1961, 1990)].groupby("month")[
                ["t2m_c", "t2m_min_c", "t2m_max_c"]].mean()
            wc = worldclim[worldclim.area_name == area].set_index("month")
            if temp_delta is not None:
                bc.temp_delta[area] = temp_delta[area]
            else:
                bc.temp_delta[area] = {
                    "t2m_c": (wc.wc_tavg_c - ref.t2m_c).to_dict(),
                    "t2m_min_c": (wc.wc_tmin_c - ref.t2m_min_c).to_dict(),
                    "t2m_max_c": (wc.wc_tmax_c - ref.t2m_max_c).to_dict(),
                }

            # Lluvia: quantile mapping empírico ERA5 -> referencia (GPM o CHIRPS), periodo común
            both = g.dropna(subset=[rain_ref, "precip_era5_mm"])
            if qm_years:
                both = both[both.year.between(*qm_years)]
            bc.qm[area] = {}
            for month in range(1, 13):
                s = both[both.month.isin(_season(month))]
                bc.qm[area][month] = (np.quantile(s.precip_era5_mm, QM_QUANTILES),
                                      np.quantile(s[rain_ref], QM_QUANTILES))
        # Umbrales de referencia (sobre datos ya corregidos)
        corrected = bc.apply(daily.drop(columns=["month", "year"]))
        ref = corrected[corrected.date.dt.year.between(*REF_PERIOD)]
        for area, g in ref.groupby("area_name"):
            wet = g.precip_mm[g.precip_mm >= WET_DAY]
            bc.thresholds[area] = {
                "rain_p95": float(wet.quantile(0.95)),
                "soil_p90": float(g.swvl1_m3m3.quantile(0.90)),
                "rain_annual_mean": float(g.groupby(g.date.dt.year).precip_mm.sum().mean()),
                "rain_rainy_mean": float(g[g.date.dt.month.isin(RAINY_MONTHS)]
                                         .groupby(g.date.dt.year).precip_mm.sum().mean()),
            }
        return bc

    # ---- aplicación ---------------------------------------------------------------
    def apply(self, daily: pd.DataFrame) -> pd.DataFrame:
        """Devuelve copia con temperaturas corregidas y columna `precip_mm` homogénea 1961→."""
        out = []
        for area, g in daily.groupby("area_name"):
            g = g.copy()
            month = g.date.dt.month
            for var, delta in self.temp_delta[area].items():
                g[var] = g[var] + month.map(delta).to_numpy()
            g["precip_mm"] = 0.0
            for mth in range(1, 13):
                sel = (month == mth).to_numpy()
                if sel.any():
                    g.loc[sel, "precip_mm"] = _qmap(g.precip_era5_mm.to_numpy()[sel], *self.qm[area][mth])
            if self.use_obs and self.rain_ref in g.columns:
                g["precip_mm"] = g[self.rain_ref].where(g[self.rain_ref].notna(), g.precip_mm)
            out.append(g)
        return pd.concat(out).sort_values(["area_name", "date"]).reset_index(drop=True)


def _qmap(x, q_src, q_dst):
    """Mapea x de la distribución fuente a la destino. Por encima del máximo observado
    extrapola con la razón de los cuantiles más altos (conserva extremos de El Niño)."""
    y = np.interp(x, q_src, q_dst)
    top = x > q_src[-1]
    if top.any():
        ratio = q_dst[-1] / q_src[-1] if q_src[-1] > 0 else 1.0
        y[top] = x[top] * ratio
    return np.maximum(y, 0.0)


# ══════════════════════════════════════════════════════════════════════════════════════
# 3. Derivadas diarias y agregación anual
# ══════════════════════════════════════════════════════════════════════════════════════
def add_daily_derived(daily: pd.DataFrame, bc: BiasCorrection) -> pd.DataFrame:
    """Añade HR, ET0 e indicadores diarios 0/1. `daily` ya debe estar corregido (bc.apply)."""
    d = daily.copy()
    # El delta de temperatura media se aplica también al punto de rocío (misma masa de
    # aire): así la HR de ERA5 se conserva en vez de caer artificialmente al calentar T.
    td = d.dewpoint_c + _td_delta(d, bc)
    d["rh_pct"] = relative_humidity(d.t2m_c, td)
    lat = d.area_name.map(lambda a: bc.meta[a]["lat"]).to_numpy()
    elev = d.area_name.map(lambda a: bc.meta[a]["elev_m"]).to_numpy()
    d["et0_mm"] = et0_penman_monteith(d.t2m_max_c, d.t2m_min_c, td,
                                      d.ssrd_mjm2, d.wind10m_ms, d.date.dt.day_of_year, lat, elev)
    t, rh, p = d.t2m_c, d.rh_pct, d.precip_mm
    d["fav_monilia"] = ((rh >= RH_MONILIA) & t.between(*T_MONILIA)).astype(int)
    d["fav_phyto"] = ((p >= RAIN_PHYTO) & (rh >= RH_PHYTO) & t.between(*T_PHYTO)).astype(int)
    d["wet_day"] = (p >= WET_DAY).astype(int)
    d["heavy_rain"] = (p >= HEAVY_RAIN).astype(int)
    d["rain_gt_p95"] = (p >= d.area_name.map(lambda a: bc.thresholds[a]["rain_p95"]).to_numpy()).astype(int)
    d["saturated"] = (d.swvl1_m3m3 >= d.area_name.map(
        lambda a: bc.thresholds[a]["soil_p90"]).to_numpy()).astype(int)
    return d


def _td_delta(d: pd.DataFrame, bc: BiasCorrection) -> np.ndarray:
    """Delta mensual de temperatura media, aplicado al punto de rocío."""
    month = d.date.dt.month.to_numpy()
    areas = d.area_name.to_numpy()
    lut = {(a, m): v for a, dd in bc.temp_delta.items() for m, v in dd["t2m_c"].items()}
    return np.fromiter((lut[(a, m)] for a, m in zip(areas, month)), float, len(d))


def _max_run(x: np.ndarray) -> int:
    """Racha más larga de 1 consecutivos."""
    best = cur = 0
    for v in x:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def yearly_features(d: pd.DataFrame, bc: BiasCorrection, months=RAINY_MONTHS) -> pd.DataFrame:
    """Una fila por (area_name, year) con las features de la ventana `months` de ese año.

    Además añade aptitud ECOCROP anual y la lluvia de oct–dic del año anterior
    (inicio de la temporada lluviosa de El Niño).
    """
    d = d.assign(year=d.date.dt.year, month=d.date.dt.month)
    w = d[d.month.isin(months)]
    g = w.groupby(["area_name", "year"])
    f = g.agg(
        n_days=("precip_mm", "size"),
        rain_total=("precip_mm", "sum"),
        rain_max_1d=("precip_mm", "max"),
        wet_days=("wet_day", "sum"),
        heavy_rain_days=("heavy_rain", "sum"),
        rain_p95_days=("rain_gt_p95", "sum"),
        fav_days_monilia=("fav_monilia", "sum"),
        fav_days_phytophthora=("fav_phyto", "sum"),
        saturated_days=("saturated", "sum"),
        rh_mean=("rh_pct", "mean"),
        t_mean=("t2m_c", "mean"),
        tmax_mean=("t2m_max_c", "mean"),
        tmin_mean=("t2m_min_c", "mean"),
        et0_total=("et0_mm", "sum"),
        solar_mean=("ssrd_mjm2", "mean"),
    )
    if "modis_evi" in w.columns:                    # MODIS (2000→): verdor medio de la ventana
        f["evi_jan_jun"] = g.modis_evi.mean() * 1e-4
    f["rain_max_5d"] = g.precip_mm.apply(lambda s: s.rolling(5).sum().max())
    f["max_wet_spell"] = g.wet_day.apply(lambda s: _max_run(s.to_numpy()))
    f["water_balance"] = f.rain_total - f.et0_total

    # Anual (año calendario): aptitud ECOCROP y exceso sobre el óptimo de lluvia
    ann = d.groupby(["area_name", "year"]).agg(t_annual=("t2m_c", "mean"),
                                               rain_annual=("precip_mm", "sum"),
                                               days=("precip_mm", "size"))
    ann["rain_annual"] = ann.rain_annual * 365.25 / ann.days       # años parciales
    ann["suit"] = ecocrop_suitability(ann.t_annual, ann.rain_annual)
    f["suitability"] = ann.suit.reindex(f.index)
    f["rain_excess_opt"] = (ann.rain_annual - ECOCROP_R[2]).clip(lower=0).reindex(f.index)
    f["rain_annual"] = ann.rain_annual.reindex(f.index)

    # Anomalía relativa de lluvia respecto a la normal del área (comparable entre provincias)
    # (la normal viene de bc, no de los datos recibidos: funciona igual con un solo año en la API)
    f = f.reset_index()
    normal = f.area_name.map(lambda a: bc.thresholds[a]["rain_rainy_mean"])
    f["rain_anom_pct"] = 100 * (f.rain_total * (181.25 / f.n_days) / normal - 1)

    # Oct–dic del año anterior
    ond = (d[d.month.isin([10, 11, 12])].groupby(["area_name", "year"])
           .agg(rain_prev_ond=("precip_mm", "sum"), fav_phyto_prev_ond=("fav_phyto", "sum")).reset_index())
    ond["year"] += 1
    f = f.merge(ond, on=["area_name", "year"], how="left")
    return f


CLIMATE_FEATURES = [
    "rain_total", "rain_anom_pct", "rain_max_1d", "rain_max_5d", "wet_days", "max_wet_spell",
    "heavy_rain_days", "rain_p95_days", "fav_days_monilia", "fav_days_phytophthora",
    "saturated_days", "rh_mean", "t_mean", "tmax_mean", "tmin_mean", "et0_total", "solar_mean",
    "water_balance", "suitability", "rain_excess_opt", "rain_prev_ond", "fav_phyto_prev_ond",
]


def build_features(daily: pd.DataFrame, bc: BiasCorrection, months=RAINY_MONTHS) -> pd.DataFrame:
    """Atajo: clima diario crudo -> features anuales."""
    return yearly_features(add_daily_derived(bc.apply(daily), bc), bc, months)
