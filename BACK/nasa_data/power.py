"""NASA POWER: clima mensual por punto. No necesita cuenta ni clave."""
import httpx
import pandas as pd

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

# parámetro POWER -> id de variable en Supabase
PARAMS = {
    "T2M": "t2m",
    "T2M_MAX": "t2m_max",
    "T2M_MIN": "t2m_min",
    "RH2M": "rh2m",
    "ALLSKY_SFC_SW_DWN": "solar_rad",
    "WS2M": "ws2m",
    "PRECTOTCORR": "precip_power",  # mm/día, útil para comparar con GPM
}


def power_monthly(lon: float, lat: float, start_year: int = 2020, end_year: int = 2024) -> pd.DataFrame:
    r = httpx.get(URL, params={
        "parameters": ",".join(PARAMS), "community": "AG",
        "longitude": lon, "latitude": lat,
        "start": start_year, "end": end_year, "format": "JSON",
    }, timeout=60)
    r.raise_for_status()
    data = r.json()["properties"]["parameter"]

    rows: dict[str, dict] = {}
    for p, var_id in PARAMS.items():
        for key, val in data[p].items():          # key = YYYYMM; MM=13 es el anual
            if key.endswith("13"):
                continue
            rows.setdefault(key, {})[var_id] = None if val == -999 else val
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.to_datetime(df.index, format="%Y%m")
    return df.rename_axis("month_date").reset_index().sort_values("month_date", ignore_index=True)
