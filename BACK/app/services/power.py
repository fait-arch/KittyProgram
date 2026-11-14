"""Proxy de NASA POWER (sin key) con caché: clima de cualquier punto."""
import calendar

import httpx

from ..core.cache import cached
from ..core.config import get_settings
from ..core.errors import unavailable

PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN,WS2M"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


@cached(ttl=24 * 3600, maxsize=512)
def climatology(lat: float, lon: float) -> dict:
    """lat/lon ya redondeados a 2 decimales por el router (≈1 km) para reutilizar la caché."""
    url = f"{get_settings().nasa_power_url}/temporal/climatology/point"
    try:
        r = httpx.get(url, params={"parameters": PARAMS, "community": "AG", "latitude": lat,
                                   "longitude": lon, "format": "JSON"}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise unavailable("power_unavailable", f"NASA POWER no respondió: {e}")
    p = data["properties"]["parameter"]
    monthly = {k: {str(i + 1): v.get(m) for i, m in enumerate(MONTHS)} for k, v in p.items()}
    # PRECTOTCORR viene en mm/día → mm/mes y mm/año
    pr = p.get("PRECTOTCORR", {})
    precip_month = {str(i + 1): round((pr.get(m) or 0) * calendar.monthrange(2025, i + 1)[1], 1) for i, m in enumerate(MONTHS)}
    return {
        "point": {"lat": lat, "lon": lon},
        "elevation_m": (data.get("geometry", {}).get("coordinates") or [None, None, None])[2],
        "source": "NASA POWER (community AG, climatología)", "resolution_km": 55,
        "monthly_climatology": monthly,
        "precip_mm_month": precip_month,
        "annual": {"t2m": (p.get("T2M") or {}).get("ANN"), "rh2m": (p.get("RH2M") or {}).get("ANN"),
                   "precip_mm": round(sum(precip_month.values()), 1)},
    }
