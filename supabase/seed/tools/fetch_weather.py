"""Descarga clima diario (reanálisis ERA5 + ERA5-Land ("era5_seamless") vía Open-Meteo) para el seed de pruebas.

Uso:  python fetch_weather.py <carpeta_raw>

Lee  <raw>/adm1.geojson, adm2.geojson, oni.txt, sstoi.txt
Crea <raw>/areas.json            (provincias y cantones con su punto representativo)
     <raw>/weather/<clave>_<ini>_<fin>.json   (caché: se puede relanzar sin repetir llamadas)

Alcance (para respetar los límites gratuitos de Open-Meteo):
  · Provincias: serie diaria completa 2001–2025.
  · Cantones:   enero–junio de un año Niño y un año neutro recientes.
"""
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import shape

RAW = Path(sys.argv[1])
WX = RAW / "weather"
WX.mkdir(exist_ok=True)

PROVINCES = {  # nombre normalizado -> (código DPA INEC, región)
    "el oro": ("07", "costa"), "esmeraldas": ("08", "costa"), "guayas": ("09", "costa"),
    "los rios": ("12", "costa"), "manabi": ("13", "costa"),
    "santo domingo de los tsachilas": ("23", "costa"),
    "morona santiago": ("14", "amazonia"), "napo": ("15", "amazonia"), "pastaza": ("16", "amazonia"),
    "zamora chinchipe": ("19", "amazonia"), "sucumbios": ("21", "amazonia"), "orellana": ("22", "amazonia"),
}
# Años de cantones (ene–jun), en orden de prioridad. Clase ENSO según la regla anual:
#   Niño: 2025, 2024, 2023, 2016, 2015 · neutro: 2020, 2018, 2014 · Niña: 2022
CANTON_YEARS = [2025, 2020, 2024, 2023, 2018, 2016, 2015, 2022, 2014]
DAILY = ("temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
         "relative_humidity_2m_mean,precipitation_sum,soil_moisture_0_to_7cm_mean")
API = "https://archive-api.open-meteo.com/v1/archive"


def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def build_areas() -> list[dict]:
    adm1 = json.loads((RAW / "adm1.geojson").read_text(encoding="utf-8"))["features"]
    adm2 = json.loads((RAW / "adm2.geojson").read_text(encoding="utf-8"))["features"]
    provs, areas = [], []
    for f in adm1:
        k = key(f["properties"]["shapeName"])
        if k in PROVINCES:
            g = shape(f["geometry"])
            p = g.representative_point()
            provs.append((k, g))
            areas.append({"key": "p_" + k.replace(" ", "_"), "kind": "province",
                          "name": f["properties"]["shapeName"], "name_key": k, "province_key": None,
                          "dpa": PROVINCES[k][0], "region": PROVINCES[k][1],
                          "lat": round(p.y, 4), "lon": round(p.x, 4)})
    for f in adm2:
        g = shape(f["geometry"])
        p = g.representative_point()
        for pk, pg in provs:
            if pg.contains(p):
                k = key(f["properties"]["shapeName"])
                areas.append({"key": "c_" + pk.replace(" ", "_") + "__" + k.replace(" ", "_"),
                              "kind": "canton", "name": f["properties"]["shapeName"], "name_key": k,
                              "province_key": pk, "dpa": None, "region": PROVINCES[pk][1],
                              "lat": round(p.y, 4), "lon": round(p.x, 4)})
                break
    return areas


def enso_years() -> dict[int, str]:
    """Misma regla que la vista v_enso_year_class (promedio enero–junio)."""
    mid = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6}
    oni, n12 = {}, {}
    for line in (RAW / "oni.txt").read_text().splitlines()[1:]:
        s, y, _t, a = line.split()
        if s in mid:
            oni.setdefault(int(y), []).append(float(a))
    for line in (RAW / "sstoi.txt").read_text().splitlines()[1:]:
        p = line.split()
        if 1 <= int(p[1]) <= 6:
            n12.setdefault(int(p[0]), []).append(float(p[3]))
    out = {}
    for y in oni:
        o = sum(oni[y]) / len(oni[y])
        n = sum(n12[y]) / len(n12[y]) if y in n12 else None
        out[y] = "nino" if (o >= 0.5 or (n is not None and n >= 0.4)) else "nina" if o <= -0.5 else "neutral"
    return out


def fetch(area: dict, start: str, end: str, pause: float) -> str:
    out = WX / f"{area['key']}_{start}_{end}.json"
    if out.exists():
        return "cache"
    q = urllib.parse.urlencode({"latitude": area["lat"], "longitude": area["lon"],
                                "start_date": start, "end_date": end, "daily": DAILY,
                                "models": "era5_seamless", "timezone": "America/Guayaquil"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=120) as r:
                out.write_bytes(r.read())
            time.sleep(pause)
            return "ok"
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            if e.code == 429 and "inutely" in body:
                time.sleep(65)
                continue
            print("  HTTP", e.code, body[:160], flush=True)
            return "limit" if e.code == 429 else "error"
        except Exception as e:  # red inestable: reintentar
            print("  reintento:", e, flush=True)
            time.sleep(10)
    return "error"


def main() -> None:
    areas = build_areas()
    (RAW / "areas.json").write_text(json.dumps(areas, ensure_ascii=False, indent=1), encoding="utf-8")
    provs = [a for a in areas if a["kind"] == "province"]
    cants = [a for a in areas if a["kind"] == "canton"]
    print(f"{len(provs)} provincias, {len(cants)} cantones", flush=True)

    (RAW / "canton_years.json").write_text(json.dumps(CANTON_YEARS))
    cls = enso_years()
    print("años de cantones:", {y: cls.get(y) for y in CANTON_YEARS}, flush=True)

    stop = False
    for a in provs:
        for y0 in range(2001, 2026, 5):
            r = fetch(a, f"{y0}-01-01", f"{min(y0 + 4, 2025)}-12-31", pause=14)
            if r != "cache":
                print(a["key"], y0, r, flush=True)
            if r == "limit":
                stop = True
                break
        if stop:
            break
    if not stop:
        for y in CANTON_YEARS:                      # año por año: una parada por límite deja todo balanceado
            n = 0
            for a in cants:
                r = fetch(a, f"{y}-01-01", f"{y}-06-30", pause=1.6)
                n += r == "ok"
                if r == "limit":
                    stop = True
                    break
            print("cantones año", y, "descargados:", n, flush=True)
            if stop:
                break
    print("FIN", "(detenido por límite)" if stop else "(completo)", flush=True)


if __name__ == "__main__":
    main()
