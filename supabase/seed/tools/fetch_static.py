"""Datos fijos por área: altitud y pendiente (SRTM 30 m) y suelo (SoilGrids 250 m).

Uso:  python fetch_static.py <carpeta_raw>
Lee   <raw>/areas.json, adm1.geojson, adm2.geojson
Crea  <raw>/static.json   (se guarda al avanzar: se puede relanzar sin repetir llamadas)

Altitud/pendiente: hasta 16 puntos dentro del polígono; en cada uno se pide el valor central y
los 4 vecinos a ~100 m → pendiente = atan(|gradiente|). Se promedian los puntos.
  API: https://api.opentopodata.org/v1/srtm30m  (1 petición/s, ≤ 100 puntos por llamada)
Suelo: SoilGrids v2 en los primeros puntos del polígono con dato (0–30 cm, media ponderada).
  API: https://rest.isric.org/soilgrids/v2.0/properties/query  (≈ 5 peticiones/min)
"""
import json
import math
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import Point, shape

RAW = Path(sys.argv[1])
OUT = RAW / "static.json"
D = 0.0009  # ≈ 100 m
M_LAT = 110574.0


def key(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def http_json(url, retries=4, wait=15):
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                time.sleep(wait * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(wait)
    return None


def samples(geom, n=16):
    minx, miny, maxx, maxy = geom.bounds
    k = 1
    while True:  # rejilla cada vez más fina hasta tener ≥ n puntos dentro
        pts = [Point(minx + (i + 0.5) * (maxx - minx) / (k * 4), miny + (j + 0.5) * (maxy - miny) / (k * 4))
               for i in range(k * 4) for j in range(k * 4)]
        pts = [p for p in pts if geom.contains(p)]
        if len(pts) >= n or k >= 8:
            break
        k += 1
    if not pts:
        pts = [geom.representative_point()]
    step = max(1, len(pts) // n)
    return pts[::step][:n]


def terrain(pts):
    locs = []
    for p in pts:
        y, x = p.y, p.x
        locs += [(y, x), (y + D, x), (y - D, x), (y, x + D), (y, x - D)]
    url = "https://api.opentopodata.org/v1/srtm30m?locations=" + "|".join(f"{a:.5f},{b:.5f}" for a, b in locs)
    d = http_json(url)
    time.sleep(1.2)
    if not d or d.get("status") != "OK":
        return None
    z = [r["elevation"] for r in d["results"]]
    elev, slopes = [], []
    for i, p in enumerate(pts):
        c, n, s, e, w = z[5 * i: 5 * i + 5]
        if None in (c, n, s, e, w):
            continue
        dx = 2 * D * 111320 * math.cos(math.radians(p.y))
        dy = 2 * D * M_LAT
        slopes.append(math.degrees(math.atan(math.hypot((e - w) / dx, (n - s) / dy))))
        elev.append(c)
    if not elev:
        return None
    slopes.sort()
    return {"elevation_mean_m": sum(elev) / len(elev), "slope_mean_deg": sum(slopes) / len(slopes),
            "slope_p90_deg": slopes[min(len(slopes) - 1, int(0.9 * len(slopes)))], "n_points": len(elev)}


def usda_texture(sand, clay):
    silt = 100 - sand - clay
    if silt + 1.5 * clay < 15: return "arenoso"
    if silt + 1.5 * clay < 30 and silt + 2 * clay >= 15: return "franco arenoso"
    if clay >= 40 and silt >= 40: return "arcillo limoso"
    if clay >= 40 and sand > 45: return "arcilloso arenoso"
    if clay >= 40: return "arcilloso"
    if clay >= 35 and sand > 45: return "arcillo arenoso"
    if clay >= 27 and sand <= 20: return "franco arcillo limoso"
    if clay >= 27 and sand <= 45: return "franco arcilloso"
    if clay >= 27: return "franco arcillo arenoso"
    if silt >= 80 and clay < 12: return "limoso"
    if silt >= 50 and clay >= 12 or (silt >= 50 and clay < 12): return "franco limoso"
    if clay >= 7 and clay < 20 and sand > 52: return "franco arenoso"
    return "franco"


def soil(pts):
    for p in pts[:4]:
        q = ("https://rest.isric.org/soilgrids/v2.0/properties/query?" +
             urllib.parse.urlencode([("lon", f"{p.x:.5f}"), ("lat", f"{p.y:.5f}"), ("property", "phh2o"), ("property", "clay"),
                                      ("property", "sand"), ("property", "soc"), ("depth", "0-5cm"), ("depth", "5-15cm"),
                                      ("depth", "15-30cm"), ("value", "mean")]))
        d = http_json(q, wait=20)
        time.sleep(13)  # ≈ 5 peticiones/min
        if not d:
            continue
        out = {}
        w = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
        for L in d["properties"]["layers"]:
            num = den = 0
            for dp in L["depths"]:
                v = dp["values"].get("mean")
                if v is not None:
                    num += v / L["unit_measure"]["d_factor"] * w[dp["label"]]
                    den += w[dp["label"]]
            if den:
                out[L["name"]] = num / den
        if len(out) == 4:
            return {"soil_ph": out["phh2o"], "clay_pct": out["clay"], "sand_pct": out["sand"],
                    "soil_organic_c_gkg": out["soc"], "texture_class": usda_texture(out["sand"], out["clay"])}
    return None


def main():
    areas = json.loads((RAW / "areas.json").read_text(encoding="utf-8"))
    adm1 = {key(f["properties"]["shapeName"]): shape(f["geometry"])
            for f in json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]}
    adm2 = {}
    for f in json.loads((RAW / "adm2.geojson").read_text(encoding="utf-8"))["features"]:
        adm2.setdefault(key(f["properties"]["shapeName"]), []).append(shape(f["geometry"]))
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    # primero provincias y cantones, en el orden del archivo
    for i, a in enumerate(areas):
        if a["key"] in res and res[a["key"]].get("_done"):
            continue
        if a["kind"] == "province":
            g = adm1[a["name_key"]]
        else:
            pg = adm1[a["province_key"]]
            g = next((x for x in adm2[a["name_key"]] if pg.contains(x.representative_point())), adm2[a["name_key"]][0])
        pts = samples(g)
        r = {"_done": False}
        t = terrain(pts)
        if t:
            r.update(t)
        s = soil(pts)
        if s:
            r.update(s)
        r["_done"] = True
        res[a["key"]] = r
        OUT.write_text(json.dumps(res, ensure_ascii=False))
        print(i + 1, "/", len(areas), a["key"], {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if k != "_done"}, flush=True)
    print("FIN", len(res), flush=True)


if __name__ == "__main__":
    main()
