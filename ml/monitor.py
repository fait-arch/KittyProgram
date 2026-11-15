"""Monitor de humedad del suelo (NASA SMAP L4, ~3 días de retraso) para seguir la temporada en curso.

    ml/.venv/bin/python -m ml.etl.satellite_extra   # SMAP del país y provincias hasta hoy (GEE)
    ml/.venv/bin/python -m ml.etl.smap_cantons      # SMAP de los 125 cantones (lote mensual)
    ml/.venv/bin/python -m ml.monitor               # → artifacts/monitor_soil_v1.csv

Por área (país, provincias, 125 cantones) y mes:
    z           = (humedad superficial media del mes − media del mismo mes 2015–2025) / desviación
    saturado %  = % de días con humedad ≥ percentil 90 del área (2015–2025) — el análogo satelital de
                  los "días con suelo encharcado" que usa el modelo
    estado      seco (z ≤ −1 y ≤ −10 % del normal) · normal · húmedo (z ≥ 1 y ≥ +10 %) ·
                encharcado (z ≥ 2 y ≥ +20 %, o saturado ≥ 50 % de los días)

Sirve para ir actualizando el escenario `actual` durante la temporada: si en ene–jun 2027 el suelo
de la costa pasa a "encharcado", el riesgo de un año como 1998 sube. Además valida el vínculo con el
modelo: correlación entre los días saturados de SMAP y los de ERA5 (ene–jun 2015–2025).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .config import ARTIFACTS, DATA_PROCESSED, DATA_RAW, ROOT
from .etl.cantons import RAW as RAW_CANT

REF = (2015, 2025)
OUT = ARTIFACTS / "monitor_soil_v1"


def load_smap() -> pd.DataFrame:
    files = sorted((DATA_RAW / "gee" / "smap").glob("*.parquet")) + sorted((RAW_CANT / "smap_batch").glob("*.parquet"))
    d = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    d["date"] = pd.to_datetime(d.date)
    d = d.dropna(subset=["smap_sm_surface_m3m3"]).drop_duplicates(["area_name", "date"])
    ids = pd.read_csv(ROOT / "data" / "cantons_supabase.csv", dtype=str).id
    from .etl.areas import slug
    by_slug = {slug(i): i for i in ids}
    d["area_name"] = d.area_name.map(lambda s: by_slug.get(slug(s), s))
    return d[["date", "area_name", "smap_sm_surface_m3m3"]].rename(columns={"smap_sm_surface_m3m3": "sm"})


def status(z: float, sat: float, rel: float) -> str:
    """rel = % sobre la humedad normal del mes (evita llamar 'encharcado' a +5 % donde casi no varía)."""
    if pd.isna(z):
        return None
    if sat >= 50 or (z >= 2 and rel >= 20):
        return "encharcado"
    if z >= 1 and rel >= 10:
        return "humedo"
    return "seco" if (z <= -1 and rel <= -10) else "normal"


def run(verbose=True) -> pd.DataFrame:
    d = load_smap()
    d = d.assign(year=d.date.dt.year, month=d.date.dt.month)
    ref = d[d.year.between(*REF)]
    p90 = ref.groupby("area_name").sm.quantile(0.9).rename("p90")
    d = d.merge(p90, on="area_name")
    d["sat"] = (d.sm >= d.p90).astype(int)
    mon = d.groupby(["area_name", "year", "month"]).agg(sm=("sm", "mean"), sat_pct=("sat", "mean"),
                                                        days=("sm", "size"), last=("date", "max")).reset_index()
    mon["sat_pct"] *= 100
    clim = mon[mon.year.between(*REF)].groupby(["area_name", "month"]).sm.agg(["mean", "std"]).reset_index()
    mon = mon.merge(clim, on=["area_name", "month"])
    mon["z"] = (mon.sm - mon["mean"]) / mon["std"]
    mon["estado"] = [status(z, s, 100 * (sm / mu - 1)) for z, s, sm, mu in zip(mon.z, mon.sat_pct, mon.sm, mon["mean"])]

    # validación: días saturados SMAP vs ERA5 (ene–jun) en provincias y país
    era = pd.read_parquet(DATA_PROCESSED / "features_area_year.parquet")[["area_name", "year", "saturated_days"]]
    sj = d[d.month <= 6].groupby(["area_name", "year"]).sat.sum().rename("smap_sat_days").reset_index()
    v = era.merge(sj, on=["area_name", "year"])
    v = v.assign(**{c: v[c] - v.groupby("area_name")[c].transform("mean") for c in ("saturated_days", "smap_sat_days")})
    r_val = float(v.saturated_days.corr(v.smap_sat_days)) if len(v) > 5 else np.nan

    # ids y nombres de Supabase
    cant = pd.read_csv(ROOT / "data" / "cantons_supabase.csv", dtype=str).set_index("id")
    prov = pd.read_csv(ROOT / "data" / "provinces_supabase.csv", dtype=str).dropna(subset=["model_name"]).set_index("model_name")
    is_c = mon.area_name.isin(cant.index)
    mon["kind"] = np.where(is_c, "canton", np.where(mon.area_name == "national", "country", "province"))
    mon["area_id"] = np.where(is_c, mon.area_name, mon.area_name.map(prov.id))
    mon["name"] = np.where(is_c, mon.area_name.map(cant.name), mon.area_name.map(prov.name))
    mon["province"] = np.where(is_c, mon.area_name.map(cant.province), np.where(mon.kind == "province", mon.name, None))
    out = mon.dropna(subset=["area_id"])[["area_id", "kind", "name", "province", "year", "month", "sm", "mean", "z",
                                         "sat_pct", "estado", "days", "last"]]
    out = out.rename(columns={"sm": "sm_m3m3", "mean": "sm_normal_mes_m3m3", "sat_pct": "dias_saturados_pct",
                              "last": "ultimo_dato"})
    out["vs_normal_pct"] = 100 * (out.sm_m3m3 / out.sm_normal_mes_m3m3 - 1)
    out.round(3).to_csv(f"{OUT}.csv", index=False)
    out.round(3).to_parquet(f"{OUT}.parquet", index=False)
    if verbose:
        last = out.ultimo_dato.max()
        print(f"SMAP hasta {last.date()} · {out.area_id.nunique()} áreas · validación SMAP vs ERA5 (días saturados ene–jun, "
              f"dentro de área): r = {r_val:.2f}")
        cur = out[(out.year == last.year) & (out.month >= last.month - 2)]
        top = cur[cur.kind != "canton"].pivot_table(index="name", columns="month", values="z").round(2)
        print("Anomalía de humedad del suelo (z) de los últimos meses, país y provincias:"); print(top.to_string())
        lastm = cur[(cur.month == cur.month.max()) & (cur.kind == "canton")]
        print("Cantones por estado (último mes):", lastm.estado.value_counts().to_dict())
        ref98 = out[(out.kind == "country")].groupby("year").z.mean().round(2)
        print("País, z medio anual:", ref98.to_dict())
    return out


if __name__ == "__main__":
    run()
