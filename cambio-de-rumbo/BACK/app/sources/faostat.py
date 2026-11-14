"""Fuente 11 — FAOSTAT: serie nacional 1961→ (la API pide token → descarga masiva ZIP).

Filtra Area = Ecuador, Item = Cocoa beans, elementos Area harvested / Yield / Production.
Destino: `crop_production_stats` (nivel país).
"""
import zipfile
from pathlib import Path

import pandas as pd

from app.core.cache import download
from app.core.config import settings

ELEMENTS = ["Area harvested", "Yield", "Production"]


def zip_path() -> Path:
    return settings.data_raw_path / "faostat" / Path(settings.FAOSTAT_BULK_URL).name


def ensure_zip(force: bool = False) -> Path:
    """Descarga el ZIP (~decenas de MB) solo si no existe."""
    p = zip_path()
    if force or not p.exists():
        download(settings.FAOSTAT_BULK_URL, p)
    return p


def load_country_series(area: str = "Ecuador", item: str | None = None) -> pd.DataFrame:
    """Devuelve columnas: year, element, unit, value (formato largo)."""
    item = item or settings.FAOSTAT_ITEM
    with zipfile.ZipFile(ensure_zip()) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv") and "flag" not in n.lower()]
        normalized = [n for n in csvs if "normalized" in n.lower()]
        name = (normalized or csvs)[0]
        with z.open(name) as f:
            df = pd.read_csv(f, encoding="latin-1", low_memory=False)

    df = df[(df["Area"] == area) & (df["Item"] == item) & (df["Element"].isin(ELEMENTS))]

    if "Year" in df.columns and "Value" in df.columns:  # formato largo (Normalized)
        out = df[["Year", "Element", "Unit", "Value"]]
    else:  # formato ancho: columnas Y1961, Y1962...
        years = [c for c in df.columns if c.startswith("Y") and c[1:].isdigit()]
        out = df.melt(id_vars=["Element", "Unit"], value_vars=years, var_name="Year", value_name="Value")
        out["Year"] = out["Year"].str[1:].astype(int)

    out = out.rename(columns={"Year": "year", "Element": "element", "Unit": "unit", "Value": "value"})
    return out.dropna(subset=["value"]).sort_values(["element", "year"]).reset_index(drop=True)
