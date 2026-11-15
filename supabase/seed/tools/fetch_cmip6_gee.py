"""Proyecciones NASA NEX-GDDP-CMIP6 por Google Earth Engine (NASA/GDDP-CMIP6), calculadas en el servidor.

Uso:  python fetch_cmip6_gee.py <raw>     (requiere earthengine authenticate + GEE_PROJECT en BACK/.env)
Caché: <raw>/cmip6_gee/<modelo>__<escenario>__<mes>.json  → {provincia: {t, rh, p, fav_monilia, fav_phytophthora, fav_escoba_bruja}}

Para cada modelo × escenario × mes, sobre TODOS los días del periodo (histórico 1995–2014, futuro 2041–2060):
  t  = media de tas (°C) · rh = media de hurs (%) · p = media de pr (mm/día)
  fav_* = fracción de días que cumplen la regla diaria de disease_thresholds (misma que build_seed.py):
    moniliasis    HR ≥ 80 y 20 ≤ T ≤ 28
    mazorca negra lluvia ≥ 1 mm y HR ≥ 85 y 20 ≤ T ≤ 30
    escoba bruja  HR ≥ 80 y 20 ≤ T ≤ 30
Media sobre el polígono de cada provincia (celdas de 0.25°).
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
from shapely.geometry import mapping, shape

RAW = Path(sys.argv[1])
OUT = RAW / "cmip6_gee"
OUT.mkdir(parents=True, exist_ok=True)
ENV = Path(__file__).resolve().parents[3] / "BACK" / ".env"
PROJECT = os.environ.get("GEE_PROJECT") or next(
    (l.split("=", 1)[1].strip() for l in ENV.read_text().splitlines() if l.startswith("GEE_PROJECT=")), None)
ee.Initialize(project=PROJECT)

MODELS = ["ACCESS-CM2", "EC-Earth3", "GFDL-ESM4", "MRI-ESM2-0"]
PERIODS = {"historical": (1995, 2014), "ssp245": (2041, 2060), "ssp585": (2041, 2060)}


def key(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


areas = [a for a in json.loads((RAW / "areas.json").read_text(encoding="utf-8")) if a["kind"] == "province"]
adm1 = {key(f["properties"]["shapeName"]): shape(f["geometry"])
        for f in json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]}
FC = ee.FeatureCollection([ee.Feature(ee.Geometry(mapping(adm1[a["name_key"]].simplify(0.01, preserve_topology=True))),
                                      {"key": a["key"]}) for a in areas])


def daily(img):
    t = img.select("tas").subtract(273.15)
    rh = img.select("hurs")
    p = img.select("pr").multiply(86400)
    mon = rh.gte(80).And(t.gte(20)).And(t.lte(28))
    phy = p.gte(1).And(rh.gte(85)).And(t.gte(20)).And(t.lte(30))
    esc = rh.gte(80).And(t.gte(20)).And(t.lte(30))
    return ee.Image.cat([t.rename("t"), rh.rename("rh"), p.rename("p"), mon.rename("fav_monilia"),
                         phy.rename("fav_phytophthora"), esc.rename("fav_escoba_bruja")]).toFloat()


def job(args):
    model, scen, m = args
    fp = OUT / f"{model}__{scen}__{m:02d}.json"
    if fp.exists():
        return "cache"
    y0, y1 = PERIODS[scen]
    col = (ee.ImageCollection("NASA/GDDP-CMIP6").filter(ee.Filter.eq("model", model))
           .filter(ee.Filter.eq("scenario", scen)).filterDate(f"{y0}-01-01", f"{y1 + 1}-01-01")
           .filter(ee.Filter.calendarRange(m, m, "month")))
    for attempt in range(4):
        try:
            img = col.map(daily).mean()
            res = img.reduceRegions(FC, ee.Reducer.mean(), 27830, tileScale=4).getInfo()
            out = {f["properties"]["key"]: {k: f["properties"].get(k) for k in
                                            ("t", "rh", "p", "fav_monilia", "fav_phytophthora", "fav_escoba_bruja")}
                   for f in res["features"]}
            out["_n_days"] = col.size().getInfo()
            fp.write_text(json.dumps(out))
            return "ok"
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(15 * (attempt + 1))
    return f"error {model} {scen} {m}: {str(err)[:150]}"


def main():
    jobs = [(mo, sc, m) for mo in MODELS for sc in PERIODS for m in range(1, 13)]
    print(f"{len(jobs)} consultas ({len(areas)} provincias)", flush=True)
    t0, n = time.time(), {"ok": 0, "cache": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, r in enumerate(ex.map(job, jobs), 1):
            n["error" if r.startswith("error") else r] += 1
            if r.startswith("error"):
                print("  ", r, flush=True)
            if i % 12 == 0:
                print(f"{i}/{len(jobs)} {n} {time.time() - t0:.0f}s", flush=True)
    print("FIN", n, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
