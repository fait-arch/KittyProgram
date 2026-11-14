"""Fuente 12 — SIPA (MAG): precios de cacao en grano seco. Descarga manual.

1. http://sipa.agricultura.gob.ec/ → precios → cacao en grano seco (USD por quintal)
2. Guardar como BACK/data/raw/sipa/precios_cacao.csv  (columnas: fecha, usd_qq)
Destino: `crop_prices`.
"""
import pandas as pd

from app.core.config import settings

KG_PER_QUINTAL = 45.36
QQ_PER_TONNE = 1000 / KG_PER_QUINTAL  # ≈ 22.05


def usd_qq_to_usd_t(usd_qq: float) -> float:
    return round(usd_qq * QQ_PER_TONNE, 2)


def load_prices(filename: str = "precios_cacao.csv") -> pd.DataFrame:
    path = settings.data_raw_path / "sipa" / filename
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}. Descárgalo de sipa.agricultura.gob.ec")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
    df["usd_t"] = df["usd_qq"].astype(float).map(usd_qq_to_usd_t)
    return df.dropna(subset=["fecha"])
