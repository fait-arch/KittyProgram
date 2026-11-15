"""Partes 08–11 del seed: datos que faltaban, generados desde las descargas de esta máquina.

    python -I supabase/seed/tools/build_extra.py supabase/seed/raw supabase/seed/data

  08_clima_cantones.sql   Clima de cantones que faltaba (ene–jun 2014, 2015, 2016, 2022; Open-Meteo / ERA5),
                          misma lógica que build_seed.py (month_stats, RULES) + recálculo EN SQL de los
                          escenarios normal / Niño / Niña de TODOS los cantones con lo que haya en la base.
  09_nasa_satelital.sql   Earth Engine, media sobre el polígono de las 138 áreas: NDVI (+anomalía), temperatura de
                          superficie, evapotranspiración (MODIS), humedad del suelo (SMAP, GLDAS), lluvia GPM
                          IMERG (variable nueva precip_gpm) y cobertura del suelo (WorldCover).
  10_proyecciones_2050.sql NASA NEX-GDDP-CMIP6 por Earth Engine (4 modelos): cambio mensual 2041–2060 vs 1995–2014
                          (método delta) → area_scenario_climate ssp245_2050 / ssp585_2050 para provincias y
                          cantones, aptitud ECOCROP futura y matriz de zonas (provincias).
  11_precios_ecuador.sql  Precio al productor de cacao en Ecuador (FAOSTAT): mensual 2012–2022, anual 1991–2024.
  12_precio_sipa.sql      Precio al productor SIPA (MAG), mensual 2014–2024, desde las fichas de cacao (sipa_fichas.py).

Ninguna parte se ejecuta aquí. Se cargan con: python supabase/seed/inject.py --only 8,9,10,11
(después de las partes 01–07). Cada archivo es una transacción y se puede volver a aplicar (upsert).
"""
import csv
import io
import json
import sys
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path

RAW = Path(sys.argv[1])
OUT = Path(sys.argv[2])
NS = uuid.UUID("6f1c0a9e-5b7e-4f0a-9a52-0c0a11ce0001")   # mismo namespace que build_seed.py


def uid(k: str) -> str:
    return str(uuid.uuid5(NS, k))


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(round(v, 4))
    return "'" + str(v).replace("'", "''") + "'"


def values(rows) -> str:
    return ",\n".join("(" + ",".join(lit(x) for x in r) + ")" for r in rows)


def chunked(head: str, rows: list, tail: str, n: int = 5000) -> str:
    """Varias sentencias insert de ≤ n filas (evita sentencias gigantes en el pooler de Supabase)."""
    return "\n\n".join(f"{head}\n{values(rows[i:i + n])}\n{tail};" for i in range(0, len(rows), n))


def write(name: str, body: str) -> None:
    (OUT / name).write_text(body, encoding="utf-8")
    print(f"  → {OUT / name} ({len(body) / 1024:,.0f} KB)", flush=True)


AREAS = json.loads((RAW / "areas.json").read_text(encoding="utf-8"))
PROV = [a for a in AREAS if a["kind"] == "province"]
CANT = [a for a in AREAS if a["kind"] == "canton"]

# ═════════════════════════════════ 08 · clima de cantones ═════════════════════════════════
# Copia exacta de build_seed.py (RULES, SAT, longest, month_stats) para que los números coincidan.
RULES = {
    "monilia": lambda t, rh, p: rh >= 80 and 20 <= t <= 28,
    "phytophthora": lambda t, rh, p: p >= 1 and rh >= 85 and 20 <= t <= 30,
    "escoba_bruja": lambda t, rh, p: rh >= 80 and 20 <= t <= 30,
}
SAT = 0.45


def longest(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def month_stats(days: dict, y: int, m: int):
    recs = [days[k] for k in sorted(days) if k.startswith(f"{y}-{m:02d}-")]
    recs = [r for r in recs if r[0] is not None and r[1] is not None]
    if len(recs) < 20:
        return None
    t = [r[0] for r in recs]
    rh = [r[1] for r in recs]
    p = [(r[2] or 0.0) for r in recs]
    sm = [r[3] for r in recs if r[3] is not None]
    n = len(recs)
    tx = [r[4] for r in recs if r[4] is not None]
    tn = [r[5] for r in recs if r[5] is not None]
    hz = {"t2m_max_mean": (sum(tx) / len(tx)) if tx else None, "t2m_min_mean": (sum(tn) / len(tn)) if tn else None,
          "frost_days": sum(x < 2 for x in tn), "precip_total_mm": sum(p), "wet_days": sum(x >= 1 for x in p),
          "heavy_rain_days": sum(x >= 50 for x in p), "max_consecutive_wet_days": longest([x >= 1 for x in p]),
          "rh_mean": sum(rh) / n, "humid_days": sum(x >= 80 for x in rh), "t2m_mean": sum(t) / n,
          "hot_days": sum(x > 32 for x in t), "saturated_days": sum(x >= SAT for x in sm), "n_days_with_data": n,
          "sm_mean": (sum(sm) / len(sm)) if sm else None}
    risk = {}
    for pid, rule in RULES.items():
        fl = [rule(t[i], rh[i], p[i]) for i in range(n)]
        risk[pid] = (sum(fl), longest(fl), sum(fl) / n)
    return hz, risk


def part08() -> None:
    wx = RAW / "weather"
    series, hazard, risk_rows, got = [], [], [], defaultdict(int)
    VARMAP = {"t2m": "t2m_mean", "rh_mean": "rh_mean", "precip": "precip_total_mm", "soil_moisture_surf": "sm_mean",
              "t2m_max": "t2m_max_mean", "t2m_min": "t2m_min_mean", "frost_days": "frost_days", "wet_days": "wet_days",
              "heavy_rain_days": "heavy_rain_days", "hot_days": "hot_days", "saturated_days": "saturated_days"}
    for a in CANT:
        for fp in sorted(wx.glob(a["key"] + "_*.json")):
            d = json.loads(fp.read_text(encoding="utf-8"))
            if "daily" not in d:
                continue
            D = d["daily"]
            days = {t: (D["temperature_2m_mean"][i], D["relative_humidity_2m_mean"][i], D["precipitation_sum"][i],
                        D["soil_moisture_0_to_7cm_mean"][i], D["temperature_2m_max"][i], D["temperature_2m_min"][i])
                    for i, t in enumerate(D["time"])}
            y = int(D["time"][0][:4])
            for m in range(1, 13):
                r = month_stats(days, y, m)
                if not r:
                    continue
                hz, rk = r
                md = f"{y}-{m:02d}-01"
                for vid, kv in VARMAP.items():
                    if hz[kv] is not None:
                        series.append([uid(a["key"]), vid, md, hz[kv], None])
                hazard.append([uid(a["key"]), md] + [hz[k] for k in ("precip_total_mm", "wet_days", "heavy_rain_days",
                              "max_consecutive_wet_days", "rh_mean", "humid_days", "t2m_mean", "hot_days",
                              "saturated_days", "n_days_with_data")])
                for pid, (fd, mc, ri) in rk.items():
                    risk_rows.append([uid(a["key"]), pid, md, fd, round(ri, 4), mc, hz["n_days_with_data"]])
            got[y] += 1
    if not hazard:
        print("08: sin descargas de cantones; se omite", flush=True)
        return
    print("08: cantones × año descargados:", dict(sorted(got.items())), flush=True)
    write("08_clima_cantones.sql", f"""-- 08 — Clima de cantones que faltaba (Open-Meteo era5_seamless, ene–jun) + escenarios de cantones
-- Generado por supabase/seed/tools/build_extra.py. Cantones × año: {dict(sorted(got.items()))}
-- Misma lógica que build_seed.py (month_stats, RULES, SAT = {SAT}). No pisa lo ya cargado (on conflict do nothing).
-- Paso final: recalcula EN SQL los escenarios normal / Niño / Niña de TODOS los cantones con las tablas
-- de la base (area_monthly_hazard, disease_risk_monthly) y la regla única v_enso_year_class.
begin;

{chunked("insert into public.area_monthly_series (area_id, variable_id, month_date, value, anomaly) values", series, "on conflict (area_id, variable_id, month_date) do nothing")}

{chunked("insert into public.area_monthly_hazard (area_id, month_date, precip_total_mm, wet_days, heavy_rain_days, max_consecutive_wet_days, rh_mean, humid_days, t2m_mean, hot_days, saturated_days, n_days_with_data) values", hazard, "on conflict (area_id, month_date) do nothing")}

{chunked("insert into public.disease_risk_monthly (area_id, pathogen_id, month_date, favorable_days, risk_index, max_consecutive_favorable_days, n_days_with_data) values", risk_rows, "on conflict (area_id, pathogen_id, month_date) do nothing")}

-- Escenarios históricos de cantones (composite por clase ENSO del año), igual que build_seed.py
delete from public.area_scenario_climate s using public.areas a
 where a.id = s.area_id and a.kind = 'canton' and s.scenario_id in ('normal','nino','nina') and s.method = 'composite';
delete from public.disease_risk_scenario s using public.areas a
 where a.id = s.area_id and a.kind = 'canton' and s.scenario_id in ('normal','nino','nina');

insert into public.area_scenario_climate (area_id, scenario_id, variable_id, month, value_mean, value_min, value_max, n_members, method)
select h.area_id, case e.enso_class when 'neutral' then 'normal' else e.enso_class end, v.vid,
       extract(month from h.month_date)::smallint, avg(v.val), min(v.val), max(v.val), count(*), 'composite'
  from public.area_monthly_hazard h
  join public.areas a on a.id = h.area_id and a.kind = 'canton'
  join public.v_enso_year_class e on e.year = extract(year from h.month_date) and e.year between 2001 and 2025
  cross join lateral (values ('t2m', h.t2m_mean), ('rh_mean', h.rh_mean), ('precip', h.precip_total_mm)) v(vid, val)
 where v.val is not null
 group by 1, 2, 3, 4;

insert into public.disease_risk_scenario (area_id, pathogen_id, scenario_id, month, risk_mean, risk_min, risk_max, favorable_days)
select d.area_id, d.pathogen_id, case e.enso_class when 'neutral' then 'normal' else e.enso_class end,
       extract(month from d.month_date)::smallint, avg(d.risk_index), min(d.risk_index), max(d.risk_index), avg(d.favorable_days)
  from public.disease_risk_monthly d
  join public.areas a on a.id = d.area_id and a.kind = 'canton'
  join public.v_enso_year_class e on e.year = extract(year from d.month_date) and e.year between 2001 and 2025
 group by 1, 2, 3, 4;

commit;
-- Comprobar: select scenario_id, count(distinct area_id) from public.disease_risk_scenario s join public.areas a on a.id = s.area_id
--            where a.kind = 'canton' group by 1;   -- debería aparecer 'nina'
""")


# ═════════════════════════════ 09 · NASA satelital (Earth Engine) ═════════════════════════════
GEE_VARS = {   # variable: (source_id, nota)
    "ndvi": "modis_ndvi", "lst_day": "modis_lst", "et_actual": "modis_et",
    "soil_moisture_root": "smap_l4", "soil_moisture_long": "gldas", "precip_gpm": "gpm_imerg",
}


def part09() -> None:
    gd = RAW / "gee"
    keys = {a["key"]: uid(a["key"]) for a in AREAS}
    series = defaultdict(dict)   # (area_key, var) -> {YYYY-MM: valor}
    for fp in gd.glob("*_*.json"):
        if fp.stem == "land_cover":
            continue
        var, y = fp.stem.rsplit("_", 1)
        for ak, months in json.loads(fp.read_text()).items():
            for m, v in months.items():
                series[(ak, var)][f"{y}-{int(m):02d}"] = v
    rows, per_var = [], defaultdict(int)
    for (ak, var), vals in series.items():
        if ak not in keys:
            continue
        clim = defaultdict(list)
        for k, v in vals.items():
            clim[int(k[5:])].append(v)
        for k, v in sorted(vals.items()):
            ref = clim[int(k[5:])]
            anom = v - sum(ref) / len(ref) if len(ref) >= 5 else None
            rows.append([keys[ak], var, f"{k}-01", v, anom])
            per_var[var] += 1
            if var == "ndvi" and anom is not None:
                rows.append([keys[ak], "ndvi_anom", f"{k}-01", anom, None])
                per_var["ndvi_anom"] += 1
    lc_fp = gd / "land_cover.json"
    lc = json.loads(lc_fp.read_text()) if lc_fp.exists() else {}
    lc_rows = [[keys[k], json.dumps(v)] for k, v in lc.items() if k in keys]
    if not rows and not lc_rows:
        print("09: sin datos de Earth Engine; se omite", flush=True)
        return
    print("09: filas por variable:", dict(sorted(per_var.items())), "| cobertura:", len(lc_rows), "áreas", flush=True)
    write("09_nasa_satelital.sql", f"""-- 09 — Datos NASA por Google Earth Engine: media mensual sobre el polígono de cada área (provincias y cantones)
-- Generado por supabase/seed/tools/build_extra.py desde supabase/seed/tools/fetch_gee.py.
-- ndvi / ndvi_anom (MODIS MOD13Q1, SummaryQA ≤ 1) · lst_day (MOD11A2) · et_actual (MOD16A2GF) ·
-- soil_moisture_root (SMAP L4, 2015-04→) · soil_moisture_long (GLDAS Noah) · precip_gpm (GPM IMERG V07, NUEVA) ·
-- land_cover (ESA WorldCover 2021) en area_static_features.
-- precip_gpm es una variable nueva: la variable `precip` cargada hoy viene de ERA5 (Open-Meteo), no de GPM.
-- anomaly = valor − media del mismo mes en la serie del área (si hay ≥ 5 años).
begin;

insert into public.variables (id, name, unit, source_id, description, temporal_res) values
 ('precip_gpm', 'Lluvia mensual (GPM IMERG)', 'mm/mes', 'gpm_imerg',
  'Lluvia medida por satélite (NASA GPM IMERG V07), promedio sobre el área. Corrige el exceso de lluvia de ERA5 en la Costa.', 'monthly')
on conflict (id) do nothing;

{chunked("insert into public.area_monthly_series (area_id, variable_id, month_date, value, anomaly) values", rows, "on conflict (area_id, variable_id, month_date) do update set value = excluded.value, anomaly = excluded.anomaly")}

{"update public.area_static_features f set land_cover = v.lc::jsonb, computed_at = now() from (values" + chr(10) + values(lc_rows) + chr(10) + ") v(area_id, lc) where f.area_id = v.area_id::uuid;" if lc_rows else ""}

commit;
""")


# ═════════════════════════════════ 10 · CMIP6 2050 ═════════════════════════════════
def part10() -> None:
    # Fuente: tools/fetch_cmip6_gee.py (Earth Engine, NASA/GDDP-CMIP6, periodos completos de 20 años).
    # data[(prov, modelo, escenario, var)][mes] = [media]; frac[(prov, modelo, escenario, mes, patógeno)] = [fracción]
    cm = RAW / "cmip6_gee"
    data = defaultdict(lambda: defaultdict(list))
    frac = defaultdict(list)
    for fp in cm.glob("*.json"):
        model, scen, mo = fp.stem.split("__")
        for pk, v in json.loads(fp.read_text()).items():
            if pk.startswith("_") or v.get("t") is None:
                continue
            m = int(mo)
            for var, k in (("tas", "t"), ("pr", "p"), ("hurs", "rh")):
                data[(pk, model, scen, var)][m].append(v[k])
            for pid in RULES:
                frac[(pk, model, scen, m, pid)].append(v[f"fav_{pid}"])
    if not data:
        print("10: sin datos CMIP6 (correr tools/fetch_cmip6_gee.py); se omite", flush=True)
        return

    def mean(x):
        return sum(x) / len(x) if x else None

    delta = []   # province_id, scenario_id, month, var, delta_mean, delta_min, delta_max, n_models
    models = sorted({k[1] for k in data})
    for a in PROV:
        for scen, sid in (("ssp245", "ssp245_2050"), ("ssp585", "ssp585_2050")):
            for m in range(1, 13):
                for var in ("tas", "pr", "hurs"):
                    ds = []
                    for mod in models:
                        h = mean(data[(a["key"], mod, "historical", var)].get(m, []))
                        f = mean(data[(a["key"], mod, scen, var)].get(m, []))
                        if h is None or f is None:
                            continue
                        ds.append((f - h) if var != "pr" else ((f - h) / h * 100 if h > 0 else 0.0))
                    if ds:
                        delta.append([uid(a["key"]), sid, m, var, mean(ds), min(ds), max(ds), len(ds)])
    rdelta = []   # province_id, scenario_id, pathogen, month, d_mean, d_min, d_max, n_models
    for a in PROV:
        for scen, sid in (("ssp245", "ssp245_2050"), ("ssp585", "ssp585_2050")):
            for m in range(1, 13):
                for pid in RULES:
                    ds = []
                    for mod in models:
                        h, f = frac.get((a["key"], mod, "historical", m, pid)), frac.get((a["key"], mod, scen, m, pid))
                        if h and f:
                            ds.append(mean(f) - mean(h))
                    if ds:
                        rdelta.append([uid(a["key"]), sid, pid, m, mean(ds), min(ds), max(ds), len(ds)])
    print(f"10: {len(delta)} deltas de clima y {len(rdelta)} de riesgo ({len(models)} modelos: {', '.join(models)})", flush=True)
    if not delta:
        print("10: aún no hay pares histórico/futuro completos; se omite", flush=True)
        return
    write("10_proyecciones_2050.sql", f"""-- 10 — Proyecciones 2050 (NASA NEX-GDDP-CMIP6), método delta
-- Generado por supabase/seed/tools/build_extra.py desde Earth Engine (NASA/GDDP-CMIP6), tools/fetch_cmip6_gee.py.
-- Modelos: {', '.join(models)} · r1i1p1f1 · TODOS los días de 1995–2014 (histórico) y 2041–2060 (SSP2-4.5, SSP5-8.5).
-- Delta mensual por provincia (media sobre el polígono, celdas 0.25°): tas y hurs aditivos (°C, puntos de %),
-- pr relativo (%). Se aplica al clima "normal" observado de cada provincia y de sus cantones (ERA5).
-- ⚠ Hereda el sesgo de lluvia de ERA5 en la Costa (docs/08 § 4.2).
-- Riesgo 2050: fracción de días favorables (reglas de disease_thresholds sobre tas/hurs/pr diarios de cada
--   modelo), delta futuro − histórico por modelo, sumado al riesgo "normal" observado (ERA5). Recortado a 0–1.
-- Zonas: apta si aptitud ≥ 0.6; riesgo alto si el riesgo medio ene–jun 2050 (3 patógenos) ≥ 0.6. POR VALIDAR.
begin;

create temporary table _delta (province_id uuid, scenario_id text, month smallint, var text,
                               d_mean numeric, d_min numeric, d_max numeric, n_models smallint) on commit drop;
insert into _delta values
{values(delta)};

create temporary table _rdelta (province_id uuid, scenario_id text, pathogen_id text, month smallint,
                                d_mean numeric, d_min numeric, d_max numeric, n_models smallint) on commit drop;
{"insert into _rdelta values" + chr(10) + values(rdelta) + ";" if rdelta else "-- (sin series diarias: no hay delta de riesgo)"}

-- Áreas destino: cada provincia y sus cantones heredan el delta de la provincia
create temporary table _target on commit drop as
select a.id as area_id, coalesce(case when a.kind = 'province' then a.id end, a.parent_id) as province_id
  from public.areas a where a.kind in ('province', 'canton');

delete from public.area_scenario_climate where scenario_id in ('ssp245_2050', 'ssp585_2050');

-- Clima futuro = normal observado + delta (lluvia: × (1 + Δ%/100))
insert into public.area_scenario_climate (area_id, scenario_id, variable_id, month, value_mean, value_min, value_max, n_members, method)
select n.area_id, d.scenario_id, n.variable_id, n.month,
       case n.variable_id when 'precip' then n.value_mean * (1 + d.d_mean / 100) else n.value_mean + d.d_mean end,
       case n.variable_id when 'precip' then n.value_mean * (1 + d.d_min / 100) else n.value_mean + d.d_min end,
       case n.variable_id when 'precip' then n.value_mean * (1 + d.d_max / 100) else n.value_mean + d.d_max end,
       d.n_models, 'delta'
  from public.area_scenario_climate n
  join _target t on t.area_id = n.area_id
  join _delta d on d.province_id = t.province_id and d.month = n.month
               and d.var = case n.variable_id when 't2m' then 'tas' when 'precip' then 'pr' when 'rh_mean' then 'hurs' end
 where n.scenario_id = 'normal' and n.variable_id in ('t2m', 'precip', 'rh_mean');

-- Cambio proyectado como variables propias (temp_change_c, precip_change_pct)
insert into public.area_scenario_climate (area_id, scenario_id, variable_id, month, value_mean, value_min, value_max, n_members, method)
select t.area_id, d.scenario_id, case d.var when 'tas' then 'temp_change_c' else 'precip_change_pct' end, d.month,
       d.d_mean, d.d_min, d.d_max, d.n_models, 'delta'
  from _delta d join _target t on t.province_id = d.province_id
 where d.var in ('tas', 'pr');

-- Riesgo de enfermedad 2050 = riesgo "normal" observado + cambio de días favorables según los modelos
-- (mismas reglas diarias que disease_thresholds, aplicadas a tas / hurs / pr diarios de NEX-GDDP-CMIP6)
delete from public.disease_risk_scenario where scenario_id in ('ssp245_2050', 'ssp585_2050');
insert into public.disease_risk_scenario (area_id, pathogen_id, scenario_id, month, risk_mean, risk_min, risk_max, favorable_days)
select n.area_id, n.pathogen_id, d.scenario_id, n.month,
       least(1, greatest(0, n.risk_mean + d.d_mean)), least(1, greatest(0, n.risk_mean + d.d_min)),
       least(1, greatest(0, n.risk_mean + d.d_max)),
       least(1, greatest(0, n.risk_mean + d.d_mean)) * extract(day from (make_date(2050, n.month, 1) + interval '1 month - 1 day'))
  from public.disease_risk_scenario n
  join _target t on t.area_id = n.area_id
  join _rdelta d on d.province_id = t.province_id and d.pathogen_id = n.pathogen_id and d.month = n.month
 where n.scenario_id = 'normal';

-- Aptitud ECOCROP futura (provincias con los 12 meses), misma función que build_seed.py (part_score)
delete from public.crop_suitability where scenario_id in ('ssp245_2050', 'ssp585_2050');
with ann as (
  select s.area_id, s.scenario_id,
         avg(s.value_mean) filter (where s.variable_id = 't2m') as t_mean,
         sum(s.value_mean) filter (where s.variable_id = 'precip') as rain,
         count(*) filter (where s.variable_id = 't2m') as nt, count(*) filter (where s.variable_id = 'precip') as np
    from public.area_scenario_climate s join public.areas a on a.id = s.area_id and a.kind = 'province'
   where s.scenario_id in ('ssp245_2050', 'ssp585_2050') and s.variable_id in ('t2m', 'precip')
   group by 1, 2
), sc as (
  select *, case when t_mean between 21 and 32 then 1.0 when t_mean < 21 then greatest(0, (t_mean - 10) / 11.0)
                 else greatest(0, (38 - t_mean) / 6.0) end as s_t,
            case when rain between 1200 and 3000 then 1.0 when rain < 1200 then greatest(0, (rain - 900) / 300.0)
                 else greatest(0, (7600 - rain) / 4600.0) end as s_r
    from ann where nt = 12 and np = 12
)
insert into public.crop_suitability (area_id, crop_id, scenario_id, score, class, limiting_factors, details)
select area_id, 'cacao', scenario_id, least(s_t, s_r),
       case when least(s_t, s_r) >= 0.85 then 'optima' when least(s_t, s_r) >= 0.6 then 'apta'
            when least(s_t, s_r) >= 0.3 then 'marginal' else 'no_apta' end,
       array_remove(array[case when s_t < 1 then 'temp_mean' end, case when s_r < 1 then 'rain_annual' end], null),
       jsonb_build_object('temp_mean', round(s_t::numeric, 3), 'rain_annual', round(s_r::numeric, 3),
                          'temp_mean_c', round(t_mean::numeric, 2), 'rain_annual_mm', round(rain::numeric))
  from sc;

-- Matriz de zonas (provincias): aptitud futura × riesgo en años Niño
delete from public.zone_classification where future_scenario_id in ('ssp245_2050', 'ssp585_2050');
with risk as (   -- riesgo futuro (ene–jun) si existe; si no, el de años Niño actuales
  select area_id, scenario_id, avg(risk_mean) as fut_risk from public.disease_risk_scenario
   where scenario_id in ('ssp245_2050', 'ssp585_2050') and month between 1 and 6 group by 1, 2
), nino as (
  select area_id, avg(risk_mean) as nino_risk from public.disease_risk_scenario
   where scenario_id = 'nino' and month between 1 and 6 group by 1
)
insert into public.zone_classification (area_id, crop_id, future_scenario_id, zone_class, suitability_now, suitability_future, nino_risk)
select f.area_id, 'cacao', f.scenario_id,
       case when f.score >= 0.6 and coalesce(r.fut_risk, k.nino_risk, 0) < 0.6 then 'segura'
            when f.score >= 0.6 then 'manejo'
            when coalesce(r.fut_risk, k.nino_risk, 0) < 0.6 then 'transicion' else 'critica' end,
       n.score, f.score, coalesce(r.fut_risk, k.nino_risk)
  from public.crop_suitability f
  join public.crop_suitability n on n.area_id = f.area_id and n.crop_id = 'cacao' and n.scenario_id = 'normal'
  left join risk r on r.area_id = f.area_id and r.scenario_id = f.scenario_id
  left join nino k on k.area_id = f.area_id
 where f.crop_id = 'cacao' and f.scenario_id in ('ssp245_2050', 'ssp585_2050');

commit;
""")


# ═════════════════════════════════ 11 · precios Ecuador ═════════════════════════════════
def part11() -> None:
    fp = RAW / "faostat_prices.zip"
    if not fp.exists():
        print("11: falta faostat_prices.zip; se omite", flush=True)
        return
    z = zipfile.ZipFile(fp)
    rd = csv.DictReader(io.TextIOWrapper(z.open("Prices_E_Americas.csv"), encoding="latin-1"))
    rows = []
    for r in rd:
        if r["Area"] != "Ecuador" or r["Item"] != "Cocoa beans" or r["Element Code"] != "5532" and r["Element Code"] != "5530":
            continue
        if r["Element Code"] != "5530":   # 5530 = LCU/t; Ecuador está dolarizado (LCU = USD) y es el único con meses
            continue
        mc = int(r["Months Code"])
        for k, v in r.items():
            if k.startswith("Y") and len(k) == 5 and k[1:].isdigit() and v:
                y = int(k[1:])
                if mc == 7021:
                    rows.append(["cacao", f"{y}-01-01", "productor_faostat_anual", "grano_seco", float(v), "faostat"])
                elif 7001 <= mc <= 7012:
                    rows.append(["cacao", f"{y}-{mc - 7000:02d}-01", "productor_faostat", "grano_seco", float(v), "faostat"])
    rows.sort(key=lambda r: (r[2], r[1]))
    nm = sum(r[2] == "productor_faostat" for r in rows)
    print(f"11: {nm} meses + {len(rows) - nm} años de precio al productor (Ecuador)", flush=True)
    write("11_precios_ecuador.sql", f"""-- 11 — Precio al productor de cacao en Ecuador (FAOSTAT, Producer Prices), USD por tonelada
-- Generado por supabase/seed/tools/build_extra.py desde bulks-faostat.fao.org/production/Prices_E_Americas.zip
-- Ecuador está dolarizado: LCU = USD. market = 'productor_faostat' (mensual, 2012–2022) y
-- 'productor_faostat_anual' (promedio anual, 1991–2024; se guarda en el día 1 de enero del año).
-- No es SIPA/MAG (precio mayorista por quintal): es el precio pagado al productor reportado a la FAO.
begin;

insert into public.crop_prices (crop_id, month_date, market, product_form, price_usd_t, source_id) values
{values(rows)}
on conflict (crop_id, month_date, market, product_form) do update set price_usd_t = excluded.price_usd_t;

commit;
""")


# ═════════════════════════════════ 12 · precio SIPA ═════════════════════════════════
def part12() -> None:
    fp = RAW / "sipa_cacao.csv"
    if not fp.exists():
        print("12: falta raw/sipa_cacao.csv (tools/sipa_fichas.py); se omite", flush=True)
        return
    rows = []
    for r in csv.DictReader(open(fp, encoding="utf-8-sig")):
        usd_t = float(r["usd_per_qq"]) * 1000 / 45.36          # 1 qq = 100 lb = 45,36 kg (igual que build_seed.py)
        rows.append(["cacao", r["month"][:7] + "-01", "nacional", "grano_seco", round(usd_t, 2), "sipa"])
    years = sorted({r[1][:4] for r in rows})
    print(f"12: {len(rows)} meses de precio SIPA ({years[0]}–{years[-1]})", flush=True)
    write("12_precio_sipa.sql", f"""-- 12 — Precio al productor de cacao en Ecuador, SIPA (MAG), mensual {years[0]}–{years[-1]}
-- Generado por supabase/seed/tools/build_extra.py desde raw/sipa_cacao.csv, que sale de
-- supabase/seed/tools/sipa_fichas.py: gráfico "Precio Productor" de las FICHAS DEL CULTIVO DE CACAO
-- (https://sipa.agricultura.gob.ec/index.php/cacao, una ficha por año, exportadas a mano).
-- USD por quintal (100 lb) → USD/t con 1 qq = 45,36 kg. 2010–2013 sin dato en SIPA; 2019 con 10 meses.
-- market = 'nacional' (es el que usa el modelo demo y build_seed.py para precios SIPA).
begin;

insert into public.crop_prices (crop_id, month_date, market, product_form, price_usd_t, source_id) values
{values(rows)}
on conflict (crop_id, month_date, market, product_form) do update set price_usd_t = excluded.price_usd_t, source_id = excluded.source_id;

commit;
""")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else {"8", "9", "10", "11", "12"}
    for n, f in (("8", part08), ("9", part09), ("10", part10), ("11", part11), ("12", part12)):
        if n in only:
            f()
