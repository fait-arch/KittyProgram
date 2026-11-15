"""ETL de rendimiento de cacao (target del modelo) y precios al productor.

Fuentes (descargadas en ``ml/data/raw``):

* FAOSTAT bulk ``Production_Crops_Livestock_E_Americas.zip`` -> Ecuador, "Cocoa beans",
  serie nacional 1961->.
* FAOSTAT bulk ``Prices_E_Americas.zip`` -> precio al productor (USD/t), anual.
* ESPAC (INEC) tabulados ``espac/tabulados_<año>.xlsx``, tabla "SUPERFICIE, PRODUCCIÓN Y
  VENTAS, SEGÚN REGIÓN Y PROVINCIA - CACAO (Almendra seca)" (T13 en 2002-2015, T14 desde
  2016). Se suman las filas "Solo" + "Asociado" de cada provincia.

Salidas:

* ``ml/data/processed/production.parquet``: area_name, level ('national'|'province'), year,
  planted_ha, harvested_ha, production_t, yield_t_ha, source, suppressed.
* ``ml/data/processed/prices.parquet``: year, price_usd_t, source.

Uso (desde la raíz del repo)::

    ml/.venv/bin/python -m ml.etl.production [--download]
"""
from __future__ import annotations

import argparse
import re
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from ml.config import DATA_PROCESSED, DATA_RAW, PROVINCES

FAO_DIR = DATA_RAW / "faostat"
ESPAC_DIR = DATA_RAW / "espac"

FAO_PROD_URL = "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Americas.zip"
FAO_PRICES_URL = "https://bulks-faostat.fao.org/production/Prices_E_Americas.zip"

_ESPAC = "https://www.ecuadorencifras.gob.ec/documentos/web-inec/Estadisticas_agropecuarias/espac"
ESPAC_URLS = {
    **{y: f"{_ESPAC}/Publicaciones-espac/INDICE_PUBLICACION%20ESPAC%20{y}.xlsx" for y in range(2002, 2014)},
    2014: f"{_ESPAC}/espac_2014-2015/2014/Indice%20de%20publicacion%20ESPAC-2014.xlsx",
    2015: f"{_ESPAC}/espac_2014-2015/2015/Indice%20de%20publicacion%20ESPAC%202015.xlsx",
    2016: f"{_ESPAC}/espac-2016/Indice%20de%20publicacion%20ESPAC%202016.xlsx",
    2017: f"{_ESPAC}/espac_2017/Indice_de%20publicacion_ESPAC_2017.xlsx",
    2018: f"{_ESPAC}/espac-2018/Tabulados%20ESPAC%202018.xlsx",
    2019: f"{_ESPAC}/espac-2019/Tabulados%20ESPAC%202019.xlsx",
    2020: f"{_ESPAC}/espac-2020/Tabulados%20ESPAC%202020.xlsx",
    2021: f"{_ESPAC}/espac-2021/Tabulados%20ESPAC%202021.xlsx",
    2022: f"{_ESPAC}/espac_2022/Tabulados%20ESPAC%202022.xlsx",
    2023: f"{_ESPAC}/2023/Tabulados_ESPAC_2023.xlsx",
    2024: f"{_ESPAC}/2024/Tabulados_ESPAC_2024.xlsx",
    2025: f"{_ESPAC}/2025/Tabulados_excel_2025.xlsx",
}

COLUMNS = ["area_name", "level", "year", "planted_ha", "harvested_ha", "production_t",
           "yield_t_ha", "source", "suppressed"]


# --------------------------------------------------------------------------- utilidades
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_province(name: str) -> str:
    """'LOS RÍOS' -> 'Los Rios'; 'SANTO DOMINGO DE LOS TSÁCHILAS' -> 'Santo Domingo De Los Tsachilas'."""
    s = re.sub(r"\s+", " ", strip_accents(str(name)).strip()).title()
    aliases = {p.lower(): p for p in PROVINCES}
    return aliases.get(s.lower(), s)


def download(url: str, dest: Path) -> None:
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=300, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    print(f"descargado {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")


def download_all(force: bool = False) -> None:
    targets = {FAO_DIR / "Production_Crops_Livestock_E_Americas.zip": FAO_PROD_URL,
               FAO_DIR / "Prices_E_Americas.zip": FAO_PRICES_URL}
    targets.update({ESPAC_DIR / f"tabulados_{y}.xlsx": u for y, u in ESPAC_URLS.items()})
    for dest, url in targets.items():
        if force or not dest.exists():
            try:
                download(url, dest)
            except Exception as e:  # noqa: BLE001
                print(f"ERROR descargando {url}: {e}")


def _read_fao_csv(zpath: Path, suffix: str = "_NOFLAG.csv") -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith(suffix))
        with z.open(name) as f:
            return pd.read_csv(f, encoding="latin-1")


# --------------------------------------------------------------------------- FAOSTAT
def load_faostat_production() -> pd.DataFrame:
    df = _read_fao_csv(FAO_DIR / "Production_Crops_Livestock_E_Americas.zip")
    df = df[(df["Area"] == "Ecuador") & (df["Item"] == "Cocoa beans")]
    ycols = [c for c in df.columns if re.fullmatch(r"Y\d{4}", c)]
    long = df.melt(id_vars=["Element"], value_vars=ycols, var_name="year", value_name="v")
    long["year"] = long["year"].str[1:].astype(int)
    wide = long.pivot_table(index="year", columns="Element", values="v").reset_index()
    out = pd.DataFrame({
        "area_name": "Ecuador",
        "level": "national",
        "year": wide["year"],
        "planted_ha": np.nan,
        "harvested_ha": wide.get("Area harvested"),
        "production_t": wide.get("Production"),
    })
    out["yield_t_ha"] = out["production_t"] / out["harvested_ha"]
    out["source"] = "faostat"
    out["suppressed"] = False
    return out.dropna(subset=["production_t", "harvested_ha"], how="all")


def load_faostat_prices() -> pd.DataFrame:
    df = _read_fao_csv(FAO_DIR / "Prices_E_Americas.zip")
    df = df[(df["Area"] == "Ecuador") & (df["Item"] == "Cocoa beans")
            & (df["Element Code"] == 5532) & (df["Months Code"] == 7021)]  # USD/t, anual
    ycols = [c for c in df.columns if re.fullmatch(r"Y\d{4}", c)]
    long = df.melt(value_vars=ycols, var_name="year", value_name="price_usd_t").dropna()
    long["year"] = long["year"].str[1:].astype(int)
    long["source"] = "faostat"
    return long.sort_values("year").reset_index(drop=True)


# --------------------------------------------------------------------------- ESPAC
_MISSING = {".", "*", "-", "", "…", "..."}
_NON_PROVINCE = re.compile(r"^(REGI[OÓ]N|ZONAS? NO DELIMITADAS?|NORORIENTE|CENTRO-SURORIENTE|TOTAL)", re.I)


def _num(v) -> tuple[float, bool]:
    """Devuelve (valor, oculto). '*' = dato oculto por confidencialidad."""
    if v is None:
        return np.nan, False
    if isinstance(v, (int, float)):
        return float(v), False
    s = str(v).strip()
    if s in _MISSING:
        return np.nan, s == "*"
    try:
        return float(s.replace(",", "")), False
    except ValueError:
        return np.nan, False


def _sheet_key(s: str) -> str:
    return re.sub(r"[\s.]", "", str(s)).upper()


def _find_cacao_sheet(wb) -> "openpyxl.worksheet.worksheet.Worksheet":
    # 1) índice del libro: fila "T14. | ... provincia cacao (almendra seca)"
    by_key = {_sheet_key(n): n for n in wb.sheetnames}
    for r in wb.worksheets[0].iter_rows(values_only=True):
        cells = [str(c) for c in r if c is not None]
        text = " ".join(cells)
        if not (re.search(r"cacao", text, re.I) and re.search(r"provincia", text, re.I)):
            continue
        for c in cells:
            m = re.match(r"^\s*(?:TABLA\s*)?(T\s*\d+)\b", c, re.I)
            if m and _sheet_key(m.group(1)) in by_key:
                return wb[by_key[_sheet_key(m.group(1))]]
    # 2) respaldo: título dentro de la hoja
    for ws in wb.worksheets:
        if not re.match(r"^T\s*\d+\.?$", ws.title.strip()):
            continue
        head = " ".join(str(c) for r in ws.iter_rows(max_row=8, values_only=True) for c in r if c)
        if re.search(r"cacao", head, re.I) and re.search(r"provincia", head, re.I):
            return ws
    raise ValueError("no se encontró la tabla de cacao por provincia")


def parse_espac_year(path: Path, year: int) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = [list(r) for r in _find_cacao_sheet(wb).iter_rows(values_only=True)]
    wb.close()

    # columna de "Plantada": Plantada, Cosechada, Producción, Ventas en columnas consecutivas
    c0 = next(i for r in rows for i, v in enumerate(r) if isinstance(v, str) and v.strip() == "Plantada")

    recs: dict[str, dict] = {}
    national = None
    current = None
    for r in rows:
        strs = [(i, str(v).strip()) for i, v in enumerate(r[:c0]) if isinstance(v, str) and v.strip()]
        label = next((s for i, s in strs if s not in ("Solo", "Asociado")), None)
        kind = next((s for i, s in strs if s in ("Solo", "Asociado")), None)
        vals = [_num(v) for v in (r[c0:c0 + 4] + [None] * 4)[:4]]
        if label and label.upper().startswith("TOTAL NACIONAL") and national is None:
            national = vals
            continue
        if kind == "Solo" and label:
            current = None if _NON_PROVINCE.match(label) else normalize_province(label)
        elif kind is None:
            if label:
                current = None
            continue
        if current is None:
            continue
        rec = recs.setdefault(current, {"v": [np.nan] * 4, "sup": False})
        for k, (x, hidden) in enumerate(vals):
            if not np.isnan(x):
                rec["v"][k] = x if np.isnan(rec["v"][k]) else rec["v"][k] + x
            rec["sup"] |= hidden

    out = [{"area_name": p, "level": "province", "year": year, "planted_ha": d["v"][0],
            "harvested_ha": d["v"][1], "production_t": d["v"][2], "suppressed": d["sup"]}
           for p, d in recs.items()]
    if national:
        out.append({"area_name": "Ecuador", "level": "national", "year": year,
                    "planted_ha": national[0][0], "harvested_ha": national[1][0],
                    "production_t": national[2][0], "suppressed": False})
    df = pd.DataFrame(out)
    df["yield_t_ha"] = df["production_t"] / df["harvested_ha"].where(df["harvested_ha"] > 0)
    df["source"] = "espac"
    return df


def load_espac() -> pd.DataFrame:
    frames = []
    for path in sorted(ESPAC_DIR.glob("tabulados_*.xlsx")):
        year = int(re.search(r"(\d{4})", path.stem).group(1))
        try:
            df = parse_espac_year(path, year)
        except Exception as e:  # noqa: BLE001
            print(f"ESPAC {year}: ERROR {e}")
            continue
        prov = df[df.level == "province"]
        nat = df[df.level == "national"]
        if len(nat):
            gap = prov["production_t"].sum() / nat["production_t"].iloc[0] - 1
            print(f"ESPAC {year}: {len(prov)} provincias; suma prov vs total nacional {gap:+.1%}")
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--download", action="store_true", help="descargar archivos faltantes")
    ap.add_argument("--force", action="store_true", help="re-descargar todo")
    args = ap.parse_args()
    if args.download or args.force:
        download_all(force=args.force)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    parts = []
    if (FAO_DIR / "Production_Crops_Livestock_E_Americas.zip").exists():
        parts.append(load_faostat_production())
    else:
        print("FAOSTAT producción: falta el zip (usar --download)")
    parts.append(load_espac())
    prod = pd.concat(parts, ignore_index=True)[COLUMNS]
    prod["year"] = prod["year"].astype(int)
    prod["suppressed"] = prod["suppressed"].astype(bool)
    prod = prod.sort_values(["source", "level", "area_name", "year"]).reset_index(drop=True)
    prod.to_parquet(DATA_PROCESSED / "production.parquet", index=False)
    print(f"production.parquet: {len(prod)} filas")
    print(prod.groupby(["source", "level"]).agg(n=("year", "size"), y0=("year", "min"),
                                                y1=("year", "max")).to_string())

    if (FAO_DIR / "Prices_E_Americas.zip").exists():
        prices = load_faostat_prices()
        prices.to_parquet(DATA_PROCESSED / "prices.parquet", index=False)
        print(f"prices.parquet: {len(prices)} filas ({prices.year.min()}-{prices.year.max()})")


if __name__ == "__main__":
    main()
