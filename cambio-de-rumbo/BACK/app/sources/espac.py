"""Fuente 10 — ESPAC (INEC): producción de cacao por provincia. Sin API: descarga manual.

1. https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/
2. Descargar los tabulados (XLSX) por año.
3. Guardar en BACK/data/raw/espac/espac_<año>.xlsx
4. Normalizar con load_espac() → etl_production.

Destino: `crop_production_stats`, `crop_exposure`.
"""
import re
import unicodedata

import pandas as pd

from app.core.config import settings


def _norm(text: str) -> str:
    """'Los Ríos' → 'LOS RIOS' (para cruzar con FAO GAUL, que no lleva tildes)."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def list_files() -> list[str]:
    return sorted(p.name for p in (settings.data_raw_path / "espac").glob("espac_*.xls*"))


def load_espac(year: int, sheet: str | int = 0, header_row: int = 0) -> pd.DataFrame:
    """Lee un XLSX de ESPAC. Los tabulados cambian de formato entre años:
    ajustar `sheet` y `header_row` mirando el archivo la primera vez."""
    path = settings.data_raw_path / "espac" / f"espac_{year}.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}. Descárgalo de ecuadorencifras.gob.ec")
    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    df.columns = [_norm(c) for c in df.columns]
    prov_col = next((c for c in df.columns if "PROVINCIA" in c), None)
    if prov_col:
        df["province_norm"] = df[prov_col].map(_norm)
    df["year"] = year
    return df
