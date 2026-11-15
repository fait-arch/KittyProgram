"""Descarga SOLO los cantón × año que faltan en Supabase (ene–jun), con la misma función y caché
que fetch_weather.py. Uso: python fetch_weather_missing.py <raw>
Requiere <raw>/areas.json y <raw>/canton_years_in_db.json (qué años ya hay en la BD por cantón).
"""
import json
import sys
import uuid
from pathlib import Path

RAW = Path(sys.argv[1])
src = (Path(__file__).parent / "fetch_weather.py").read_text().split("def main")[0]
ns = {"__name__": "fw"}
exec(compile(src, "fetch_weather", "exec"), ns)          # reutiliza fetch(), DAILY, API y la caché
NS = uuid.UUID("6f1c0a9e-5b7e-4f0a-9a52-0c0a11ce0001")
YEARS = [2016, 2015, 2022, 2014]                          # los que faltan, en orden de prioridad

areas = [a for a in json.loads((RAW / "areas.json").read_text()) if a["kind"] == "canton"]
have = {int(y): set(v) for y, v in json.loads((RAW / "canton_years_in_db.json").read_text()).items()}
for y in YEARS:
    todo = [a for a in areas if str(uuid.uuid5(NS, a["key"])) not in have.get(y, set())]
    n = {"ok": 0, "cache": 0, "error": 0, "limit": 0}
    for a in todo:
        r = ns["fetch"](a, f"{y}-01-01", f"{y}-06-30", pause=1.6)
        n[r] += 1
        if r == "limit":
            print(f"{y}: límite diario de Open-Meteo alcanzado; relanzar mañana (retoma sin repetir)", flush=True)
            print(y, n, flush=True)
            sys.exit(2)
    print(y, f"{len(todo)} cantones →", n, flush=True)
print("FIN (completo)", flush=True)
