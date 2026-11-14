"""Fuentes 1 y 2 — NOAA CPC: ONI y Niño 1+2 / 3.4 (texto plano, sin cuenta).

Destino: tabla `enso_index` (index_id, month_date, value).
"""
from app.core.cache import cached, http_get
from app.core.config import settings

# ONI se fecha en el mes central del trimestre móvil
SEAS_MID = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
            "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}


def fetch_oni(use_cache: bool = True) -> list[dict]:
    def _get():
        txt = http_get(settings.NOAA_ONI_URL, timeout=30).text
        rows = []
        for line in txt.splitlines()[1:]:
            parts = line.split()
            if len(parts) != 4 or parts[0] not in SEAS_MID:
                continue
            seas, yr, _total, anom = parts
            rows.append({"index_id": "oni",
                         "month_date": f"{int(yr)}-{SEAS_MID[seas]:02d}-01",
                         "value": float(anom)})
        return rows

    return cached("noaa", "oni", _get, use_cache)


def fetch_nino(use_cache: bool = True) -> list[dict]:
    """Columnas: YR MON NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM."""
    def _get():
        txt = http_get(settings.NOAA_SSTOI_URL, timeout=30).text
        rows = []
        for line in txt.splitlines()[1:]:
            p = line.split()
            if len(p) < 10:
                continue
            md = f"{int(p[0])}-{int(p[1]):02d}-01"
            rows.append({"index_id": "nino12_anom", "month_date": md, "value": float(p[3])})
            rows.append({"index_id": "nino34_anom", "month_date": md, "value": float(p[9])})
        return rows

    return cached("noaa", "sstoi", _get, use_cache)


def enso_current() -> dict:
    """Último ONI y Niño 1+2, con una fase simple (umbral ±0.5)."""
    oni = fetch_oni()[-1]
    nino12 = [r for r in fetch_nino() if r["index_id"] == "nino12_anom"][-1]
    v = oni["value"]
    fase = "El Niño" if v >= 0.5 else "La Niña" if v <= -0.5 else "Neutral"
    if v >= 1.5:
        fase += " fuerte"
    return {"fase": fase, "oni": oni, "nino12": nino12,
            "fuente": "NOAA Climate Prediction Center"}
