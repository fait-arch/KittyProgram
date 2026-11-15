"""Datos NASA por Google Earth Engine: promedio mensual sobre el POLÍGONO de cada área (12 provincias + 126 cantones).

Uso:  python fetch_gee.py <raw>      (requiere `earthengine authenticate` y GEE_PROJECT en BACK/.env)
Lee <raw>/areas.json, adm1.geojson, adm2.geojson (mismos polígonos que build_seed.py).
Caché: <raw>/gee/<variable>_<año>.json  (se puede relanzar; solo baja lo que falta)

| variable            | colección GEE                        | cálculo                                   |
|---------------------|--------------------------------------|-------------------------------------------|
| ndvi                | MODIS/061/MOD13Q1 (NDVI, SummaryQA≤1)| media del mes × 0.0001                    |
| lst_day             | MODIS/061/MOD11A2 (LST_Day_1km)      | media × 0.02 − 273.15 (°C)                |
| et_actual           | MODIS/061/MOD16A2GF (ET)             | media(ET 8 días × 0.1) / 8 × días del mes |
| soil_moisture_root  | NASA/SMAP/SPL4SMGP/008 (sm_rootzone) | media (m³/m³), desde 2015-04              |
| soil_moisture_long  | NASA/GLDAS/V021/NOAH/G025/T3H        | media RootMoist_inst (kg/m²)              |
| precip_gpm          | NASA/GPM_L3/IMERG_MONTHLY_V07        | mm/h × 24 × días del mes                  |
| land_cover (static) | ESA/WorldCover/v200                  | fracción de cada clase en el polígono     |
"""
import calendar
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
from shapely.geometry import mapping, shape

RAW = Path(sys.argv[1])
OUT = RAW / "gee"
OUT.mkdir(parents=True, exist_ok=True)
ENV = Path(__file__).resolve().parents[3] / "BACK" / ".env"
PROJECT = os.environ.get("GEE_PROJECT") or next(
    (l.split("=", 1)[1].strip() for l in ENV.read_text().splitlines() if l.startswith("GEE_PROJECT=")), None)
ee.Initialize(project=PROJECT)

YEARS = range(2001, 2026)
VARS = {   # var: (colección, banda, escala m, primer año, transformación por imagen, agregación mensual)
    "ndvi": ("MODIS/061/MOD13Q1", "NDVI", 1000, 2001),
    "lst_day": ("MODIS/061/MOD11A2", "LST_Day_1km", 1000, 2001),
    "et_actual": ("MODIS/061/MOD16A2GF", "ET", 1000, 2001),
    "soil_moisture_root": ("NASA/SMAP/SPL4SMGP/008", "sm_rootzone", 11000, 2015),
    "soil_moisture_long": ("NASA/GLDAS/V021/NOAH/G025/T3H", "RootMoist_inst", 27000, 2001),
    "precip_gpm": ("NASA/GPM_L3/IMERG_MONTHLY_V07", "precipitation", 10000, 2001),
}


def key(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def build_fc() -> ee.FeatureCollection:
    """Mismos polígonos que build_seed.py: provincia = ADM1; cantón = ADM2 cuyo punto cae en su provincia."""
    areas = json.loads((RAW / "areas.json").read_text(encoding="utf-8"))
    adm1 = {key(f["properties"]["shapeName"]): shape(f["geometry"])
            for f in json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]}
    adm2 = {}
    for f in json.loads((RAW / "adm2.geojson").read_text(encoding="utf-8"))["features"]:
        adm2.setdefault(key(f["properties"]["shapeName"]), []).append(shape(f["geometry"]))
    feats = []
    for a in areas:
        if a["kind"] == "province":
            g = adm1[a["name_key"]]
        else:
            pg = adm1[a["province_key"]]
            cands = adm2[a["name_key"]]
            g = next((x for x in cands if pg.contains(x.representative_point())), cands[0])
        g = g.simplify(0.003, preserve_topology=True)
        feats.append(ee.Feature(ee.Geometry(mapping(g)), {"key": a["key"]}))
    return ee.FeatureCollection(feats)


FC = build_fc()


def monthly_image(var: str, y: int, m: int) -> ee.Image:
    col_id, band, _scale, _y0 = VARS[var]
    start = ee.Date.fromYMD(y, m, 1)
    col = ee.ImageCollection(col_id).filterDate(start, start.advance(1, "month"))
    days = calendar.monthrange(y, m)[1]
    if var == "ndvi":
        img = col.map(lambda i: i.select(band).updateMask(i.select("SummaryQA").lte(1)).multiply(0.0001)).mean()
    elif var == "lst_day":
        img = col.select(band).mean().multiply(0.02).subtract(273.15)
    elif var == "et_actual":
        img = col.select(band).mean().multiply(0.1).divide(8).multiply(days)
    elif var == "precip_gpm":
        img = col.select(band).mean().multiply(24 * days)
    else:
        img = col.select(band).mean()
    return img.rename("v").set("month", m)


def year_job(args):
    var, y = args
    fp = OUT / f"{var}_{y}.json"
    if fp.exists():
        return "cache"
    scale = VARS[var][2]
    out = {}
    for m in range(1, 13):
        if var == "soil_moisture_root" and (y, m) < (2015, 4):
            continue
        for attempt in range(4):
            try:
                res = monthly_image(var, y, m).reduceRegions(FC, ee.Reducer.mean(), scale, tileScale=4).getInfo()
                for f in res["features"]:
                    v = f["properties"].get("mean")
                    if v is not None:
                        out.setdefault(f["properties"]["key"], {})[str(m)] = v
                break
            except Exception as e:  # noqa: BLE001
                if "no bands" in str(e):   # mes aún no publicado por la NASA (p. ej. GPM con retraso): sin dato
                    break
                if attempt == 3:
                    return f"error {var} {y}-{m}: {str(e)[:120]}"
                time.sleep(10 * (attempt + 1))
    fp.write_text(json.dumps(out))
    return "ok"


def land_cover():
    fp = OUT / "land_cover.json"
    if fp.exists():
        return "cache"
    wc = ee.Image("ESA/WorldCover/v200/2021").select("Map")
    res = wc.reduceRegions(FC, ee.Reducer.frequencyHistogram(), 100, tileScale=8).getInfo()
    names = {"10": "tree", "20": "shrubland", "30": "grassland", "40": "cropland", "50": "built_up", "60": "bare",
             "70": "snow_ice", "80": "water", "90": "wetland", "95": "mangroves", "100": "moss_lichen"}
    out = {}
    for f in res["features"]:
        h = f["properties"].get("histogram") or {}
        tot = sum(h.values()) or 1
        out[f["properties"]["key"]] = {names.get(k, k): round(v / tot, 4) for k, v in h.items() if v / tot >= 0.001}
    fp.write_text(json.dumps(out))
    return "ok"


def main():
    jobs = [(v, y) for v, (_c, _b, _s, y0) in VARS.items() for y in YEARS if y >= y0]
    print(f"{len(jobs)} variable × año ({FC.size().getInfo()} áreas) + cobertura", flush=True)
    print("land_cover:", land_cover(), flush=True)
    t0, n = time.time(), {"ok": 0, "cache": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, r in enumerate(ex.map(year_job, jobs), 1):
            n["error" if r.startswith("error") else r] += 1
            if r.startswith("error"):
                print("  ", r, flush=True)
            if i % 10 == 0:
                print(f"{i}/{len(jobs)} {n} {time.time() - t0:.0f}s", flush=True)
    print("FIN", n, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
