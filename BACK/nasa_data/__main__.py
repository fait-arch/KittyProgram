"""Exporta series NASA a CSV.

    python -m nasa_data --lon -79.53 --lat -1.80 --start 2020-01-01 --end 2025-01-01 -o babahoyo.csv
    python -m nasa_data --geojson canton.geojson -o canton.csv
"""
import argparse
import json

from .power import power_monthly
from .series import VARIABLES, monthly_series


def main():
    ap = argparse.ArgumentParser(description="Descarga series mensuales NASA a CSV")
    ap.add_argument("--lon", type=float)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--geojson", help="Archivo GeoJSON (Feature, FeatureCollection o geometría)")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2025-01-01", help="exclusivo")
    ap.add_argument("--vars", default=",".join(VARIABLES), help="ids separados por coma")
    ap.add_argument("--no-power", action="store_true", help="no añadir NASA POWER")
    ap.add_argument("-o", "--out", default="nasa_series.csv")
    a = ap.parse_args()

    geom = None
    if a.geojson:
        g = json.load(open(a.geojson))
        if g.get("type") == "FeatureCollection":
            g = g["features"][0]
        geom = g.get("geometry", g)

    df = monthly_series(a.lon, a.lat, a.start, a.end, a.vars.split(","), geom)

    if not a.no_power:
        if a.lon is None:
            from shapely.geometry import shape  # opcional, solo para centroide
            c = shape(geom).centroid
            a.lon, a.lat = c.x, c.y
        pw = power_monthly(a.lon, a.lat, int(a.start[:4]), int(a.end[:4]) - 1)
        df = df.merge(pw, on="month_date", how="left")

    df.to_csv(a.out, index=False)
    print(df.round(3).to_string(index=False))
    print(f"\nGuardado en {a.out} ({len(df)} filas)")


if __name__ == "__main__":
    main()
