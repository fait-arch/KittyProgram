"""Fuente 13 — NASA POWER (API REST, sin cuenta). RESPALDO de ERA5-Land.

Celda ~55 km: en Babahoyo asume 837 m (real ≈ 12 m) y subestima la temperatura.
Usar como respaldo citado, no como fuente principal en la Costa.
Destino: `area_monthly_series` (respaldo).
"""
from app.core.cache import SourceError, cached, http_get
from app.core.config import settings

FILL = -999.0
MONTHLY_PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR"
# Para ET0 FAO-56 de respaldo (06-cache-nasa.md): viento y radiación
CLIMATOLOGY_PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR,WS2M,ALLSKY_SFC_SW_DWN"
MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _clean(v):
    return None if v is None or float(v) <= FILL else round(float(v), 3)


def _request(kind: str, lat: float, lon: float, params: dict) -> dict:
    r = http_get(f"{settings.NASA_POWER_URL}/{kind}/point", params={
        "community": "AG", "latitude": lat, "longitude": lon, "format": "JSON", **params})
    data = r.json()
    if "properties" not in data:
        raise SourceError(f"Respuesta inesperada de NASA POWER: {str(data)[:300]}")
    return data


def power_monthly(lat: float, lon: float, start_year: int | None = None,
                  end_year: int | None = None, use_cache: bool = True) -> dict:
    """Serie mensual año por año (ej. 2005–2024). Las claves 'YYYY13' (anual) se omiten."""
    lat, lon = round(lat, 2), round(lon, 2)
    start = start_year or settings.POWER_START_YEAR
    end = end_year or settings.POWER_END_YEAR

    def _get():
        raw = _request("monthly", lat, lon, {"parameters": MONTHLY_PARAMS, "start": start, "end": end})
        p = raw["properties"]["parameter"]
        filas = {}
        for param, serie in p.items():
            for yyyymm, val in serie.items():
                if yyyymm.endswith("13"):
                    continue
                md = f"{yyyymm[:4]}-{yyyymm[4:]}-01"
                filas.setdefault(md, {"month_date": md})[param.lower()] = _clean(val)
        return {"lat": lat, "lon": lon,
                "elevacion_celda_m": (raw.get("geometry", {}).get("coordinates") or [None] * 3)[2],
                "serie": sorted(filas.values(), key=lambda f: f["month_date"]),
                "fuente": "NASA POWER monthly/point, comunidad AG"}

    return cached("power", f"monthly:{lat}:{lon}:{start}:{end}", _get, use_cache)


def power_climatology(lat: float, lon: float, use_cache: bool = True) -> dict:
    """Promedio de largo plazo por mes (12 filas): para el perfil climático y ET0 de respaldo."""
    lat, lon = round(lat, 2), round(lon, 2)

    def _get():
        raw = _request("climatology", lat, lon, {"parameters": CLIMATOLOGY_PARAMS})
        p = raw["properties"]["parameter"]
        meses = []
        for i, m in enumerate(MESES, start=1):
            fila = {"mes": i}
            for param, serie in p.items():
                fila[param.lower()] = _clean(serie.get(m))
            meses.append(fila)
        return {"lat": lat, "lon": lon,
                "elevacion_celda_m": (raw.get("geometry", {}).get("coordinates") or [None] * 3)[2],
                "meses": meses,
                "fuente": "NASA POWER climatology/point, comunidad AG"}

    return cached("power", f"clim:{lat}:{lon}", _get, use_cache)
