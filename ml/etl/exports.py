"""Exportaciones de cacao de Ecuador (FAOSTAT, comercio) en equivalente de grano, 1961→.

Segunda medida, independiente, del tamaño de la cosecha nacional (aduanas vs encuesta de
producción). El target nacional usa la media geométrica de producción y exportaciones: si las dos
fuentes tienen errores de medición independientes, su media tiene menos ruido que cada una.

    export_beq_t = grano + 1.33·manteca + 1.25·pasta + 1.18·polvo        (factores ICCO)

    ml/.venv/bin/python -m ml.etl.exports        # → data/processed/exports.parquet
"""
from __future__ import annotations

import urllib.request
import zipfile

import pandas as pd

from ..config import DATA_PROCESSED, DATA_RAW

URL = "https://bulks-faostat.fao.org/production/Trade_CropsLivestock_E_Americas.zip"
ZIP = DATA_RAW / "faostat_trade" / "Trade_CropsLivestock_E_Americas.zip"
OUT = DATA_PROCESSED / "exports.parquet"
BEAN_EQUIVALENT = {"Cocoa beans": 1.0, "Cocoa butter, fat and oil": 1.33,
                   "Cocoa paste not defatted": 1.25, "Cocoa powder and cake": 1.18}


def download() -> None:
    if not ZIP.exists():
        ZIP.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, ZIP)


def load_exports() -> pd.DataFrame:
    with zipfile.ZipFile(ZIP) as z:
        df = pd.read_csv(z.open("Trade_CropsLivestock_E_Americas.csv"), encoding="latin-1",
                         low_memory=False)
    ec = df[(df.Area == "Ecuador") & (df.Element == "Export quantity")
            & df.Item.isin(BEAN_EQUIVALENT)]
    years = [c for c in ec.columns if c.startswith("Y") and c[1:].isdigit()]
    long = ec.melt(id_vars="Item", value_vars=years, var_name="year", value_name="t")
    long["year"] = long.year.str[1:].astype(int)
    long["beq_t"] = long.t.astype(float).fillna(0) * long.Item.map(BEAN_EQUIVALENT)
    out = long.groupby("year").beq_t.sum().rename("export_beq_t").reset_index()
    # precio de exportación del grano (USD/t) = valor / cantidad: sigue al precio al productor (r = 0.98)
    qty_t = ec[ec.Item == "Cocoa beans"][years].iloc[0].astype(float)
    value_kusd = df[(df.Area == "Ecuador") & (df.Item == "Cocoa beans")
                    & (df.Element == "Export value")][years].iloc[0].astype(float)
    price = pd.DataFrame({"year": [int(c[1:]) for c in years],
                          "export_price_usd_t": (value_kusd * 1000 / qty_t).to_numpy()})
    out = out.merge(price, on="year", how="left")
    return out[out.export_beq_t > 0].reset_index(drop=True)


def main():
    download()
    out = load_exports()
    out.to_parquet(OUT, index=False)
    print(f"{OUT}: {len(out)} años {out.year.min()}–{out.year.max()}")


if __name__ == "__main__":
    main()
