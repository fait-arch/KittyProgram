"""Exportaciones mensuales de cacao en grano del Banco Central del Ecuador (BCE), 1990→.

Fuente: visualizador de comercio exterior del BCE
(https://contenido.bce.fin.ec/documentos/PublicacionesNotas/bi_fw.html), consulta
"01. Por Subpartida / 22. Export. por Subpartida", mensual, subpartida 1801 (todas sus aperturas:
crudo, orgánico, los demás, tostado). Se descarga a mano en Excel y se deja en
`ml/data/raw/Externo/`.

    ml/.venv/bin/python -m ml.etl.bce     → data/processed/bce_exports_monthly.parquet
"""
from __future__ import annotations

import re
import warnings

import pandas as pd

from ..config import DATA_PROCESSED, DATA_RAW

SRC = DATA_RAW / "Externo" / "22. Export. o Import. por Subpartida.xlsx"
OUT = DATA_PROCESSED / "bce_exports_monthly.parquet"


def load() -> pd.DataFrame:
    warnings.filterwarnings("ignore", category=UserWarning)
    raw = pd.read_excel(SRC, header=None)
    hdr = raw.index[raw[1].astype(str).str.strip() == "Período"][0]
    d = raw.iloc[hdr + 1:, 1:6]
    d.columns = ["periodo", "codigo", "subpartida", "t", "fob_kusd"]
    d = d.dropna(subset=["periodo", "t"])
    m = d.periodo.astype(str).str.extract(r"(\d{4})\s*/\s*(\d{2})")
    d = d.assign(year=m[0].astype(int), month=m[1].astype(int),
                 t=pd.to_numeric(d.t, errors="coerce"), fob_kusd=pd.to_numeric(d.fob_kusd, errors="coerce"))
    out = d.groupby(["year", "month"]).agg(t=("t", "sum"), fob_kusd=("fob_kusd", "sum"),
                                           n_subpartidas=("codigo", "nunique")).reset_index()
    return out


def main():
    out = load()
    out.to_parquet(OUT, index=False)
    print(f"{OUT}: {len(out)} meses {out.year.min()}-{out.month.iloc[0]:02d} → {out.year.max()}-{out.month.iloc[-1]:02d}")


if __name__ == "__main__":
    main()
