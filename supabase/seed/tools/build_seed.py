"""Genera los archivos SQL de carga (seed) para probar la base de datos y el backend.

Uso:  python build_seed.py <carpeta_raw> <carpeta_salida> [--sample] [--no-synthetic]

Entradas (en <raw>): adm1.geojson, adm2.geojson, oni.txt, sstoi.txt, fred_cocoa.csv,
faostat_americas.zip, gbif_*.json, areas.json, weather/*.json (ver fetch_weather.py).

DATOS REALES : límites (geoBoundaries/INEC), El Niño (NOAA), clima (ERA5 vía Open-Meteo),
               producción nacional (FAOSTAT), precio (FRED/FMI), observaciones (GBIF).
DATOS SINTÉTICOS (marcados en la columna notes / fuente 'seed_sintetico'):
               producción provincial, hectáreas por cantón, modelo y predicciones DEMO.
"""
import csv
import io
import json
import math
import random
import sys
import unicodedata
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

RAW = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SAMPLE = "--sample" in sys.argv
NO_SYN = "--no-synthetic" in sys.argv   # no genera producción sintética (solo años con dato real de ESPAC)
OUT.mkdir(parents=True, exist_ok=True)
rnd = random.Random(42)

SYN = "SINTÉTICO (seed de pruebas)"
NS = uuid.UUID("6f1c0a9e-5b7e-4f0a-9a52-0c0a11ce0001")
YEAR0, YEAR1 = (2024 if SAMPLE else 2001), 2025


def uid(key: str) -> str:
    return str(uuid.uuid5(NS, key))


# ── Renderizado SQL ──────────────────────────────────────────────────────
class Raw(str):
    pass


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, (list, tuple)) and any(isinstance(x, dict) for x in v):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'"
    if isinstance(v, (list, tuple)):
        return "'{" + ",".join(str(x) for x in v) + "}'"
    if isinstance(v, dict):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'"
    return "'" + str(v).replace("'", "''") + "'"


def ins(table: str, cols: list[str], rows: list[list], conflict: str = "", chunk: int = 400) -> str:
    if not rows:
        return ""
    out = []
    for i in range(0, len(rows), chunk):
        vals = ",\n".join("(" + ",".join(lit(v) for v in r) + ")" for r in rows[i:i + chunk])
        out.append(f"insert into public.{table} ({', '.join(cols)}) values\n{vals}{conflict};\n")
    return "".join(out)


# ── Utilidades ───────────────────────────────────────────────────────────
def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def round_coords(c, nd=4):
    return [round_coords(x, nd) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], nd), round(c[1], nd)]


def geom_sql(g, tol: float) -> Raw:
    g = g.simplify(tol, preserve_topology=True)
    if not g.is_valid:  # el redondeo a 4 decimales puede crear autointersecciones
        g = make_valid(g)
    g = unary_union([x for x in getattr(g, "geoms", [g]) if x.geom_type in ("Polygon", "MultiPolygon")])
    gj0 = mapping(g)
    g = shape({"type": gj0["type"], "coordinates": round_coords(gj0["coordinates"])})
    if not g.is_valid:
        g = unary_union([x for x in getattr(make_valid(g), "geoms", [make_valid(g)]) if x.geom_type in ("Polygon", "MultiPolygon")])
    gj = mapping(g)
    gj = {"type": gj["type"], "coordinates": round_coords(gj["coordinates"])}
    txt = json.dumps(gj).replace("'", "''")
    # st_makevalid + collectionextract(…,3): la base elimina islotes degenerados (<4 puntos) tras el redondeo
    return Raw("extensions.st_multi(extensions.st_collectionextract(extensions.st_makevalid("
               "extensions.st_setsrid(extensions.st_geomfromgeojson('" + txt + "'),4326)),3))")


# ── ENSO ────────────────────────────────────────────────────────────────
MID = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
oni, n12, n3, n34, n4 = {}, {}, {}, {}, {}
for line in (RAW / "oni.txt").read_text().splitlines()[1:]:
    s, y, _t, a = line.split()
    oni[(int(y), MID[s])] = float(a)
for line in (RAW / "sstoi.txt").read_text().splitlines()[1:]:
    p = line.split()
    ym = (int(p[0]), int(p[1]))
    n12[ym], n3[ym], n4[ym], n34[ym] = float(p[3]), float(p[5]), float(p[7]), float(p[9])


def enso_class(y: int) -> str:
    o = [oni[(y, m)] for m in range(1, 7) if (y, m) in oni]
    n = [n12[(y, m)] for m in range(1, 7) if (y, m) in n12]
    if not o:
        return "neutral"
    oa, na = sum(o) / len(o), (sum(n) / len(n) if n else None)
    return "nino" if (oa >= 0.5 or (na is not None and na >= 0.4)) else "nina" if oa <= -0.5 else "neutral"


def enso_events() -> list[list]:
    rows = []
    months = sorted(oni)
    for phase, test in (("nino", lambda v: v >= 0.5), ("nina", lambda v: v <= -0.5)):
        run = []
        for ym in months + [(9999, 1)]:
            if ym in oni and test(oni[ym]) and (not run or _next(run[-1]) == ym):
                run.append(ym)
                continue
            if len(run) >= 5:
                peak = max((oni[m] for m in run), key=abs)
                a = abs(peak)
                inten = "debil" if a < 1.0 else "moderado" if a < 1.5 else "fuerte" if a < 2.0 else "muy_fuerte"
                ongoing = run[-1] == months[-1]
                rows.append([f"{phase}_{run[0][0]}_{str(run[-1][0])[2:]}" if run[-1][0] != run[0][0] else f"{phase}_{run[0][0]}",
                             phase, f"{run[0][0]}-{run[0][1]:02d}-01", None if ongoing else f"{run[-1][0]}-{run[-1][1]:02d}-01",
                             peak if phase == "nino" else None, None, inten, False, "Derivado de ONI (≥5 meses seguidos con |ONI| ≥ 0.5)"])
            run = [ym] if ym in oni and test(oni[ym]) else []
    # Niños costeros: Niño 1+2 ≥ 1.0 por ≥ 4 meses sin evento ONI fuerte en esos meses
    run = []
    mm = sorted(n12)
    for ym in mm + [(9999, 1)]:
        if ym in n12 and n12[ym] >= 1.0 and (not run or _next(run[-1]) == ym):
            run.append(ym)
            continue
        if len(run) >= 4:
            peak_o = max((oni.get(m, 0) for m in run))
            if peak_o < 1.0:
                rows.append([f"nino_costero_{run[0][0]}", "nino", f"{run[0][0]}-{run[0][1]:02d}-01",
                             f"{run[-1][0]}-{run[-1][1]:02d}-01", None, max(n12[m] for m in run),
                             "moderado", True, "Niño costero: Niño 1+2 ≥ 1.0 por ≥ 4 meses con ONI < 1.0"])
        run = [ym] if ym in n12 and n12[ym] >= 1.0 else []
    return rows


def _next(ym):
    return (ym[0] + (ym[1] == 12), 1 if ym[1] == 12 else ym[1] + 1)


# ── Territorio ──────────────────────────────────────────────────────────
areas = json.loads((RAW / "areas.json").read_text(encoding="utf-8"))
adm1 = {key(f["properties"]["shapeName"]): shape(f["geometry"])
        for f in json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]}
adm2 = {}
for f in json.loads((RAW / "adm2.geojson").read_text(encoding="utf-8"))["features"]:
    adm2.setdefault(key(f["properties"]["shapeName"]), []).append(shape(f["geometry"]))
all_adm1 = [json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]][0]

WX = RAW / "weather"


def load_weather(a: dict) -> tuple[dict, float | None]:
    days, elev = {}, None
    for fp in sorted(WX.glob(a["key"] + "_*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        if "daily" not in d:
            continue
        elev = d.get("elevation", elev)
        D = d["daily"]
        for i, t in enumerate(D["time"]):
            days[t] = (D["temperature_2m_mean"][i], D["relative_humidity_2m_mean"][i],
                       D["precipitation_sum"][i], D["soil_moisture_0_to_7cm_mean"][i],
                       D["temperature_2m_max"][i], D["temperature_2m_min"][i])
    return days, elev


if SAMPLE:
    keep = {"p_los_rios"}
    cants = [a for a in areas if a["kind"] == "canton" and a["province_key"] == "los rios"
             and list(WX.glob(a["key"] + "_*.json"))][:1]
    areas = [a for a in areas if a["key"] in keep] + cants

import openpyxl
_wb = openpyxl.load_workbook(RAW / "admgz.xlsx", read_only=True, data_only=True)
DPA_PROV = {key(r[2]): r[0] for r in list(_wb["eci_admgz_adm1"].iter_rows(values_only=True))[1:] if r[0]}
DPA_CANT = {(key(r[4]), key(r[2])): r[0] for r in list(_wb["ecu_admgz_adm2"].iter_rows(values_only=True))[1:] if r[0]}
# geoBoundaries abrevia o recorta algunos nombres; El Piedrero y Manga del Cura son "zonas no delimitadas" sin código
DPA_ALIAS = {("guayas", key("Alfredo Baquerizo Moreno")): "0902", ("guayas", key("Empalme")): "0908",
             ("guayas", key("Crnel. Marcelino Maridueña")): "0923", ("guayas", key("Gnral. Antonio Elizalde")): "0927",
             ("orellana", key("Orellana")): "2201"}
STATIC = json.loads((RAW / "static.json").read_text(encoding="utf-8")) if (RAW / "static.json").exists() else {}
for a in areas:
    a["dpa"] = (DPA_PROV.get(a["name_key"]) if a["kind"] == "province"
                else DPA_CANT.get((a["province_key"], a["name_key"])) or DPA_ALIAS.get((a["province_key"], a["name_key"])))
    a["id"] = uid(a["key"])
    a["pid"] = uid("p_" + a["province_key"].replace(" ", "_")) if a["province_key"] else None
    a["days"], a["elev"] = load_weather(a)
areas = [a for a in areas if a["days"]]
_nodpa = [f'{a["name"]} ({a["province_key"]})' for a in areas if a["dpa"] is None]
print("sin código DPA:", len(_nodpa), _nodpa[:12], flush=True)
prov = [a for a in areas if a["kind"] == "province"]
cant = [a for a in areas if a["kind"] == "canton"]
print(f"{len(prov)} provincias, {len(cant)} cantones con clima", flush=True)

# ── Clima mensual, peligros y riesgo ────────────────────────────────────
RULES = {  # espejo de disease_thresholds (migración 0005)
    "monilia": lambda t, rh, p: rh >= 80 and 20 <= t <= 28,
    "phytophthora": lambda t, rh, p: p >= 1 and rh >= 85 and 20 <= t <= 30,
    "escoba_bruja": lambda t, rh, p: rh >= 80 and 20 <= t <= 30,
}
SAT = 0.45  # umbral demo de suelo saturado (m³/m³)


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
          "frost_days": sum(x < 2 for x in tn), "precip_total_mm": sum(p), "wet_days": sum(x >= 1 for x in p), "heavy_rain_days": sum(x >= 50 for x in p),
          "max_consecutive_wet_days": longest([x >= 1 for x in p]), "rh_mean": sum(rh) / n,
          "humid_days": sum(x >= 80 for x in rh), "t2m_mean": sum(t) / n, "hot_days": sum(x > 32 for x in t),
          "saturated_days": sum(x >= SAT for x in sm), "n_days_with_data": n, "sm_mean": (sum(sm) / len(sm)) if sm else None}
    risk = {}
    for pid, rule in RULES.items():
        fl = [rule(t[i], rh[i], p[i]) for i in range(n)]
        risk[pid] = (sum(fl), longest(fl), sum(fl) / n)
    return hz, risk


MONTHS = {}  # (area_key, y, m) -> (hz, risk)
for a in areas:
    ys = range(YEAR0, YEAR1 + 1) if a["kind"] == "province" else sorted({int(d[:4]) for d in a["days"]})
    for y in ys:
        for m in range(1, 13):
            r = month_stats(a["days"], y, m)
            if r:
                MONTHS[(a["key"], y, m)] = r
print("meses calculados:", len(MONTHS), flush=True)

# ── Producción nacional real (FAOSTAT) ──────────────────────────────────
z = zipfile.ZipFile(RAW / "faostat_americas.zip")
rd = csv.DictReader(io.TextIOWrapper(z.open("Production_Crops_Livestock_E_Americas.csv"), encoding="latin-1"))
fao = defaultdict(dict)
for r in rd:
    if r["Area"] == "Ecuador" and r["Item"] == "Cocoa beans":
        for k, v in r.items():
            if k.startswith("Y") and k[1:].isdigit() and v:
                fao[r["Element"]][int(k[1:])] = float(v)
fao_years = sorted(y for y in fao["Production"] if YEAR0 <= y <= YEAR1)
all_years = sorted(y for y in fao["Production"] if 2001 <= y <= 2025)
xs = all_years
ys_ = [fao["Production"][y] / fao["Area harvested"][y] for y in xs]
mx, my = sum(xs) / len(xs), sum(ys_) / len(ys_)
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys_)) / sum((x - mx) ** 2 for x in xs)
base_yield = lambda y: my + slope * (y - mx)  # tendencia nacional (t/ha)

# ── Construcción de tablas ──────────────────────────────────────────────
parts = defaultdict(list)

# P1: fuentes + áreas + características estáticas
src = [
    ["hdx_cod_ecu", "Códigos DPA — COD-AB Ecuador (INEC / OCHA)", "INEC / OCHA ROLAC", "other", "ecu_admgz.xlsx", "static", "2024-01-01", "https://data.humdata.org/dataset/cod-ab-ecu", "CC BY-IGO — INEC, OCHA"],
    ["opentopodata", "SRTM 30 m vía OpenTopoData", "NASA / OpenTopoData", "other", "api.opentopodata.org/v1/srtm30m", "static", "2000-02-11", "https://www.opentopodata.org", "NASA SRTM; datos servidos por OpenTopoData"],
    ["seed_sintetico", "Datos sintéticos del seed de pruebas", "KittyProgram", "other", "supabase/seed", "static", None, None, "No usar como evidencia: solo para probar el sistema"],
    ["fred", "FRED — Global price of Cocoa (PCOCOUSDM)", "FMI / FRED", "other", "fredgraph.csv?id=PCOCOUSDM", "monthly", "1990-01-01", "https://fred.stlouisfed.org/series/PCOCOUSDM", "IMF Primary Commodity Prices via FRED"],
    ["open_meteo", "Open-Meteo Historical Weather (ERA5 / ERA5-Land)", "Open-Meteo / ECMWF", "other", "archive-api.open-meteo.com/v1/archive", "daily", "1940-01-01", "https://open-meteo.com", "Weather data by Open-Meteo.com (CC BY 4.0); contains modified Copernicus Climate Change Service information"],
    ["geoboundaries", "geoBoundaries ECU ADM1/ADM2", "geoBoundaries / INEC", "other", "gbOpen/ECU", "static", "2019-01-01", "https://www.geoboundaries.org", "CC BY 3.0 IGO — fuente: INEC, OCHA ROLAC"],
]
parts[1].append(ins("data_sources", ["id", "name", "provider", "access", "dataset_ref", "temporal_res", "period_start", "url", "citation"], src, " on conflict (id) do nothing"))

arows = []
tol_c, tol_p, tol_k = (0.3, 0.05, 0.05) if SAMPLE else (0.02, 0.006, 0.004)
country = unary_union(list(adm1.values()))
arows.append([uid("country_ecuador"), "country", "Ecuador", None, None, None, geom_sql(country, tol_c)])
DPA = {a["key"]: a["dpa"] for a in prov}
for a in prov:
    arows.append([a["id"], "province", a["name"], uid("country_ecuador"), a["dpa"], a["region"], geom_sql(adm1[a["name_key"]], tol_p)])
for a in cant:
    g = adm2[a["name_key"]]
    pg = adm1[a["province_key"]]
    gg = next((x for x in g if pg.contains(x.representative_point())), g[0])
    a["geom"] = gg
    arows.append([a["id"], "canton", a["name"], a["pid"], a["dpa"], a["region"], geom_sql(gg, tol_k)])
for a in prov:
    a["geom"] = adm1[a["name_key"]]
parts[1].append(ins("areas", ["id", "kind", "name", "parent_id", "inec_dpa_code", "region", "geom"], arows))
st_rows = []
for a in areas:
    st = STATIC.get(a["key"], {})
    el = st.get("elevation_mean_m", a["elev"])
    if el is None and not st:
        continue
    st_rows.append([a["id"], el, st.get("slope_mean_deg"), st.get("slope_p90_deg"), st.get("soil_ph"),
                    st.get("soil_organic_c_gkg"), st.get("clay_pct"), st.get("sand_pct"), st.get("texture_class")])
parts[1].append(ins("area_static_features", ["area_id", "elevation_mean_m", "slope_mean_deg", "slope_p90_deg", "soil_ph",
                                             "soil_organic_c_gkg", "clay_pct", "sand_pct", "texture_class"],
                    st_rows, " on conflict (area_id) do nothing"))

# P2: ENSO
er = []
for name, d in (("oni", oni), ("nino12_anom", n12), ("nino3_anom", n3), ("nino34_anom", n34), ("nino4_anom", n4)):
    for (y, m), v in sorted(d.items()):
        if y >= (2024 if SAMPLE else 1990):
            er.append([name, f"{y}-{m:02d}-01", v])
parts[2].append(ins("enso_index", ["index_id", "month_date", "value"], er, " on conflict (index_id, month_date) do nothing"))
ev = [e for e in enso_events() if int(e[2][:4]) >= (2022 if SAMPLE else 1990)]
parts[2].append(ins("enso_events", ["id", "phase", "start_month", "end_month", "peak_oni", "peak_nino12", "intensity", "is_coastal", "notes"], ev,
                    " on conflict (id) do nothing"))

# P3: serie mensual + peligros
series, hazard = [], []
clim = defaultdict(list)
for (ak, y, m), (hz, _r) in MONTHS.items():
    clim[(ak, m)].append(hz)
for (ak, y, m), (hz, _r) in sorted(MONTHS.items()):
    a = next(x for x in areas if x["key"] == ak)
    md = f"{y}-{m:02d}-01"
    VARMAP = {"t2m": "t2m_mean", "rh_mean": "rh_mean", "precip": "precip_total_mm", "soil_moisture_surf": "sm_mean",
              "t2m_max": "t2m_max_mean", "t2m_min": "t2m_min_mean", "frost_days": "frost_days", "wet_days": "wet_days",
              "heavy_rain_days": "heavy_rain_days", "hot_days": "hot_days", "saturated_days": "saturated_days"}
    for vid, key_v in VARMAP.items():
        val = hz[key_v]
        if val is None:
            continue
        norm = [c[key_v] for c in clim[(ak, m)] if c[key_v] is not None]
        anom = (val - sum(norm) / len(norm)) if a["kind"] == "province" and len(norm) > 3 else None
        series.append([a["id"], vid, md, val, anom])
    hazard.append([a["id"], md] + [hz[k] for k in ("precip_total_mm", "wet_days", "heavy_rain_days", "max_consecutive_wet_days", "rh_mean",
                                                 "humid_days", "t2m_mean", "hot_days", "saturated_days", "n_days_with_data")])
parts[3].append(ins("area_monthly_series", ["area_id", "variable_id", "month_date", "value", "anomaly"], series))
parts[3].append(ins("area_monthly_hazard", ["area_id", "month_date", "precip_total_mm", "wet_days", "heavy_rain_days", "max_consecutive_wet_days",
                                            "rh_mean", "humid_days", "t2m_mean", "hot_days", "saturated_days", "n_days_with_data"], hazard))

# P4: riesgo mensual, escenarios, aptitud
risk_rows = []
for (ak, y, m), (_hz, risk) in sorted(MONTHS.items()):
    a = next(x for x in areas if x["key"] == ak)
    for pid, (fd, mc, ri) in risk.items():
        risk_rows.append([a["id"], pid, f"{y}-{m:02d}-01", fd, round(ri, 4), mc, _hz["n_days_with_data"]])
parts[4].append(ins("disease_risk_monthly", ["area_id", "pathogen_id", "month_date", "favorable_days", "risk_index", "max_consecutive_favorable_days", "n_days_with_data"], risk_rows))

cls_year = {y: enso_class(y) for y in range(YEAR0, YEAR1 + 1)}
scen_clim, scen_risk = [], []
for a in prov + cant:
    for sc in ("normal", "nino", "nina"):
        yrs = [y for y, c in cls_year.items() if c == ("neutral" if sc == "normal" else sc)]
        if not yrs:
            continue
        for m in range(1, 13):
            sel = [MONTHS[(a["key"], y, m)] for y in yrs if (a["key"], y, m) in MONTHS]
            if not sel:
                continue
            for vid, k in (("t2m", "t2m_mean"), ("rh_mean", "rh_mean"), ("precip", "precip_total_mm")):
                vals = [s[0][k] for s in sel]
                scen_clim.append([a["id"], sc, vid, m, sum(vals) / len(vals), min(vals), max(vals), len(vals), "composite"])
            for pid in RULES:
                vals = [s[1][pid][2] for s in sel]
                scen_risk.append([a["id"], pid, sc, m, sum(vals) / len(vals), min(vals), max(vals), sum(s[1][pid][0] for s in sel) / len(sel)])
parts[4].append(ins("area_scenario_climate", ["area_id", "scenario_id", "variable_id", "month", "value_mean", "value_min", "value_max", "n_members", "method"], scen_clim))
parts[4].append(ins("disease_risk_scenario", ["area_id", "pathogen_id", "scenario_id", "month", "risk_mean", "risk_min", "risk_max", "favorable_days"], scen_risk))

REQ = {"temp_mean": (21, 32, 10, 38), "rain_annual": (1200, 3000, 900, 7600)}


def part_score(v, o1, o2, a1, a2):
    if o1 <= v <= o2:
        return 1.0
    if v < o1:
        return max(0.0, (v - a1) / (o1 - a1))
    return max(0.0, (a2 - v) / (a2 - o2))


suit = []
for a in prov:
    yrs = [y for y in range(YEAR0, YEAR1 + 1) if all((a["key"], y, m) in MONTHS for m in range(1, 13))]
    if not yrs:
        continue
    t_mean = sum(MONTHS[(a["key"], y, m)][0]["t2m_mean"] for y in yrs for m in range(1, 13)) / (12 * len(yrs))
    rain = sum(MONTHS[(a["key"], y, m)][0]["precip_total_mm"] for y in yrs for m in range(1, 13)) / len(yrs)
    sc = {"temp_mean": part_score(t_mean, *REQ["temp_mean"]), "rain_annual": part_score(rain, *REQ["rain_annual"])}
    s = min(sc.values())
    cl = "optima" if s >= 0.85 else "apta" if s >= 0.6 else "marginal" if s >= 0.3 else "no_apta"
    suit.append([a["id"], "cacao", "normal", s, cl, [k for k, v in sc.items() if v < 1], {**{k: round(v, 3) for k, v in sc.items()}, "temp_mean_c": round(t_mean, 2), "rain_annual_mm": round(rain)}])
parts[4].append(ins("crop_suitability", ["area_id", "crop_id", "scenario_id", "score", "class", "limiting_factors", "details"], suit))

# P5: producción — ESPAC (INEC) real 2023–2025 por provincia, FAOSTAT nacional real, sintética en los demás años
def parse_espac(year):
    fp = RAW / f"espac_tab{year}.xlsx"
    if not fp.exists():
        return {}
    wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
    num = None
    for r in wb["ÍNDICE"].iter_rows(values_only=True):
        t = " ".join(str(x) for x in r if x)
        if "cacao" in t.lower() and "provincia" in t.lower():
            num = t.split(".")[0].strip()
            break
    out, cur = {}, None
    for r in wb[num].iter_rows(values_only=True):
        c1 = r[1] if len(r) > 1 and isinstance(r[1], str) else None
        c2 = r[2] if len(r) > 2 and isinstance(r[2], str) else None
        if c1 is None and c2 != "Asociado":
            continue
        if c1 is not None:
            up = c1.strip().upper()
            if up.startswith(("REGIÓN", "REGION", "ZONA", "FUENTE")):
                cur = None
                continue
            cur = "__nacional__" if up == "TOTAL NACIONAL" else key(c1)
            out.setdefault(cur, [0.0, 0.0, 0.0])
        if cur is None:
            continue
        v = [x if isinstance(x, (int, float)) else 0.0 for x in r[3:7]]   # plantada, cosechada, producción, ventas
        out[cur][0] += v[0]   # superficie plantada (ha)
        out[cur][1] += v[1]   # superficie cosechada (ha)
        out[cur][2] += v[2]   # producción (t)
    return out


espac = {}
for y in range(2014, 2026):
    if not (RAW / f"espac_tab{y}.xlsx").exists():
        continue
    try:
        espac[y] = parse_espac(y)
    except Exception as e:  # formato distinto en años antiguos
        print(f"ESPAC {y}: no se pudo leer ({e}); se omite", flush=True)
espac_years = []
for y in sorted(espac):   # control: las provincias deben sumar ≈ total nacional (±2 %)
    if not espac[y] or "__nacional__" not in espac[y]:
        print(f"ESPAC {y}: sin tabla de cacao reconocible; se omite", flush=True)
        continue
    tot = sum(v[2] for k, v in espac[y].items() if k != "__nacional__")
    nat = espac[y]["__nacional__"][2]
    ok = nat > 0 and abs(tot - nat) / nat < 0.02
    print(f"ESPAC {y}: producción nacional {nat:,.0f} t; suma de provincias {tot:,.0f} t -> {'OK' if ok else 'NO CUADRA, se omite'}", flush=True)
    if ok:
        espac_years.append(y)

for a in prov:
    ys_, hs_ = [], []
    for y in espac_years:
        v = espac[y].get(a["name_key"])
        n_ = espac[y]["__nacional__"]
        if v and v[1] > 0 and n_[1] > 0:
            ys_.append((v[2] / v[1]) / (n_[2] / n_[1]))
            hs_.append(v[1] / n_[1])
    a["ratio"] = sum(ys_) / len(ys_) if ys_ else 1.0
    a["share"] = sum(hs_) / len(hs_) if hs_ else 0.005

prod = []
cid = uid("country_ecuador")
for y in fao_years:
    prod.append([cid, "cacao", y, None, None, fao["Area harvested"][y], None, fao["Production"][y], "faostat", "Dato real FAOSTAT (nacional)"])
for y in espac_years:
    if y >= YEAR0:
        n_ = espac[y]["__nacional__"]
        prod.append([cid, "cacao", y, n_[0], None, n_[1], None, n_[2], "espac", f"ESPAC {y} T14 total nacional (solo + asociado)"])
for a in prov:
    base = [sum((MONTHS[(a["key"], yy, m)][1]["monilia"][2] + MONTHS[(a["key"], yy, m)][1]["phytophthora"][2]) / 2
                for m in range(1, 7) if (a["key"], yy, m) in MONTHS) / 6 for yy in range(YEAR0, YEAR1 + 1)]
    mean_base = sum(base) / len(base)
    for y in range(YEAR0, YEAR1 + 1):
        v = espac.get(y, {}).get(a["name_key"]) if y in espac_years else None
        if v and v[1] > 0:       # dato REAL del INEC
            prod.append([a["id"], "cacao", y, v[0], None, v[1], None, v[2], "espac", f"ESPAC {y} T14 (solo + asociado)"])
            a.setdefault("ha", {})[y] = v[1]
            a.setdefault("yld", {})[y] = v[2] / v[1]
            continue
        if NO_SYN or y not in fao["Area harvested"]:
            continue
        rk = [(MONTHS[(a["key"], y, m)][1]["monilia"][2] + MONTHS[(a["key"], y, m)][1]["phytophthora"][2]) / 2
              for m in range(1, 7) if (a["key"], y, m) in MONTHS]
        if not rk:
            continue
        loss = max(0.0, min(40.0, 60 * (sum(rk) / len(rk) - mean_base))) + abs(rnd.gauss(0, 1.5))
        yld = base_yield(y) * a["ratio"] * (1 + rnd.gauss(0, 0.04)) * (1 - loss / 100)
        h = fao["Area harvested"][y] * a["share"]
        prod.append([a["id"], "cacao", y, h * 1.08, h * 1.02, h, h * loss / 100 * 0.2, yld * h, "seed_sintetico",
                     SYN + f" — pérdida sembrada {loss:.1f}% (proporciones ancladas en ESPAC)"])
        a.setdefault("ha", {})[y] = h
        a.setdefault("yld", {})[y] = yld
parts[5].append(ins("crop_production_stats", ["area_id", "crop_id", "year", "planted_ha", "productive_ha", "harvested_ha", "lost_ha", "production_t", "source_id", "notes"], prod))

expo = []
y_ref = max(espac_years) if espac_years else max(y for y in fao["Area harvested"] if y <= YEAR1)
for a in prov:
    ha = a.get("ha", {}).get(y_ref)
    if not ha:
        continue
    real = y_ref in espac_years and a["name_key"] in espac[y_ref]
    expo.append([a["id"], "cacao", y_ref, ha, "espac_direct" if real else "manual", "espac" if real else "seed_sintetico"])
    kids = [c for c in cant if c["pid"] == a["id"]]
    tot = sum(c["geom"].area for c in kids)
    for c in kids:
        c["ha_ref"] = ha * c["geom"].area / tot if tot else 0
        expo.append([c["id"], "cacao", y_ref, c["ha_ref"], "manual", "seed_sintetico"])
parts[5].append(ins("crop_exposure", ["area_id", "crop_id", "ref_year", "crop_ha", "method", "source_id"], expo))

prices = []
for r in csv.DictReader(open(RAW / "fred_cocoa.csv")):
    if r["PCOCOUSDM"] not in ("", "."):
        prices.append(["cacao", r["observation_date"], "internacional_fred", "grano_seco", float(r["PCOCOUSDM"]), "fred"])
parts[5].append(ins("crop_prices", ["crop_id", "month_date", "market", "product_form", "price_usd_t", "source_id"], [p for p in prices if p[1] >= f"{YEAR0}-01-01"]))
sipa_fp = RAW / "sipa_cacao.csv"
if sipa_fp.exists():
    sp = []
    for r in csv.DictReader(open(sipa_fp, encoding="utf-8-sig")):
        m_ = r["month"][:7] + "-01"
        v_ = float(r["usd_per_t"]) if r.get("usd_per_t") else float(r["usd_per_qq"]) * 1000 / 45.36
        sp.append(["cacao", m_, "nacional", "grano_seco", v_, "sipa"])
    parts[5].append(ins("crop_prices", ["crop_id", "month_date", "market", "product_form", "price_usd_t", "source_id"],
                        [x for x in sp if x[1] >= f"{YEAR0}-01-01"]))
    prices = sp
    print(f"SIPA: {len(sp)} meses de precio de Ecuador", flush=True)
price_now = sum(p[4] for p in sorted(prices, key=lambda x: x[1])[-12:]) / 12

# P6: modelo DEMO + predicciones + observaciones GBIF + etl_runs
mv = uid("model_demo")
parts[6].append(ins("model_versions", ["id", "name", "crop_id", "target", "algorithm", "features", "metrics", "n_samples", "is_active"],
                    [[mv, "cacao_loss_demo_sintetico", "cacao", "yield_anomaly_pct", "formula_demo",
                      ["fav_days_monilia", "fav_days_phytophthora", "risk_index_mean"],
                      {"nota": "DEMO: loss = clip(10 + 150*(riesgo_ene_jun - riesgo_medio_del_área), 0, 60). NO entrenado ni validado."}, 0, True]]))
pred = []


def window_risk(a, years):
    vals = [(MONTHS[(a["key"], y, m)][1]["monilia"][2] + MONTHS[(a["key"], y, m)][1]["phytophthora"][2]) / 2
            for y in years for m in range(1, 7) if (a["key"], y, m) in MONTHS]
    fav = [MONTHS[(a["key"], y, m)][1]["monilia"][0] for y in years for m in range(1, 7) if (a["key"], y, m) in MONTHS]
    return (sum(vals) / len(vals), sum(fav) / max(1, len(years))) if vals else None


def base_risk(a):
    allm = [(MONTHS[(a["key"], y, m)][1]["monilia"][2] + MONTHS[(a["key"], y, m)][1]["phytophthora"][2]) / 2
            for (k, y, m) in MONTHS if k == a["key"] and m <= 6]
    return sum(allm) / len(allm)


prov_by_id = {p["id"]: p for p in prov}
for a in prov + cant:
    pa = a if a["kind"] == "province" else prov_by_id.get(a["pid"])
    ha = pa.get("ha", {}).get(y_ref) if a["kind"] == "province" else a.get("ha_ref")
    ys = [v for y_, v in (pa or {}).get("yld", {}).items() if y_ in espac_years]
    yld = (sum(ys) / len(ys)) if ys else max((pa or {}).get("yld", {}).values(), default=None)
    if not ha or not yld:
        continue
    for sc in ("normal", "nino"):
        yrs = [y for y, c in cls_year.items() if c == ("neutral" if sc == "normal" else "nino")
               and any((a["key"], y, m) in MONTHS for m in range(1, 7))]
        wr = window_risk(a, yrs)
        if not wr:
            continue
        risk, fav = wr
        loss = max(0.0, min(60.0, 10 + 150 * (risk - base_risk(a))))
        lt = ha * yld * loss / 100
        rc = "bajo" if loss < 5 else "medio" if loss < 15 else "alto" if loss < 30 else "muy_alto"
        pred.append([uid(f"pred_{a['key']}_{sc}"), mv, a["id"], "cacao", sc, loss, loss * 0.7, min(100.0, loss * 1.3), ha, yld, lt, price_now, lt * price_now, rc,
                     [{"feature": "fav_days_monilia", "label": "Días favorables a moniliasis (ene–jun)", "value": round(fav, 1)},
                      {"feature": "risk_index_mean", "label": "Índice de riesgo medio", "value": round(risk, 3)},
                      {"feature": "n_years", "label": "Años usados en el escenario", "value": len(yrs)}]])
parts[6].append(ins("loss_predictions", ["id", "model_version_id", "area_id", "crop_id", "scenario_id", "loss_pct", "loss_pct_low", "loss_pct_high",
                                         "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd", "risk_class", "top_factors"], pred))

obs = []
for fn, pid in (("gbif_monilia.json", "monilia"), ("gbif_perniciosa.json", "escoba_bruja")):
    fp = RAW / fn
    if not fp.exists():
        continue
    for o in json.loads(fp.read_text(encoding="utf-8"))["results"]:
        d = (o.get("eventDate") or "")[:10] or (f"{o['year']}-01-01" if o.get("year") else None)
        if not d or len(d) != 10 or o.get("decimalLatitude") is None:
            continue
        from shapely.geometry import Point
        pt = Point(o["decimalLongitude"], o["decimalLatitude"])
        aid = next((c["id"] for c in cant if c["geom"].contains(pt)), None)
        obs.append([aid, pid, d, o["decimalLatitude"], o["decimalLongitude"], "gbif", str(o["key"]), "GBIF: " + (o.get("basisOfRecord") or "")])
parts[6].append(ins("field_observations", ["area_id", "pathogen_id", "observed_on", "lat", "lon", "source", "external_id", "notes"], obs,
                    " on conflict (source, external_id) do nothing"))
parts[6].append(ins("etl_runs", ["script", "params", "status", "rows_written", "notes"],
                    [["seed_pruebas", {"sample": SAMPLE, "years": f"{YEAR0}-{YEAR1}"}, "done", len(series) + len(hazard) + len(risk_rows), "Carga de datos de prueba (ver supabase/seed/README.md)"]]))

# ── Escritura ───────────────────────────────────────────────────────────
names = {1: "01_territorio", 2: "02_el_nino", 3: "03_clima", 4: "04_riesgo_y_escenarios", 5: "05_produccion_y_precios", 6: "06_modelo_demo_y_observaciones"}
suffix = "_muestra" if SAMPLE else ""
full = []
for n in sorted(parts):
    body = "".join(parts[n])
    (OUT / f"{names[n]}{suffix}.sql").write_text(f"-- {names[n]} — seed de pruebas (ver supabase/seed/README.md)\n" + body, encoding="utf-8")
    full.append(body)
    print(f"{names[n]}{suffix}.sql  {len(body)/1024:,.0f} KB", flush=True)
(OUT / f"seed_completo{suffix}.sql").write_text("-- Seed completo de pruebas (partes 01 a 06)\nbegin;\n" + "\n".join(full) + "\ncommit;\n", encoding="utf-8")
print("filas:", dict(areas=len(arows), series=len(series), hazard=len(hazard), risk=len(risk_rows), scen_clim=len(scen_clim),
                     scen_risk=len(scen_risk), suit=len(suit), prod=len(prod), expo=len(expo), prices=len(prices), pred=len(pred), obs=len(obs), enso=len(er)))
