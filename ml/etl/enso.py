"""ETL ENSO: ONI + Niño 1+2 / Niño 3.4 (NOAA CPC).

Ejecutar desde la raíz del repo:
    ml/.venv/bin/python -m ml.etl.enso

Fuentes (texto plano, sin cuenta):
  - ONI (ERSSTv5, trimestres móviles, 1950→)  oni.ascii.txt
  - ERSSTv5 Niño mensual (1950→, base 1991-2020)  ersst5.nino.mth.91-20.ascii
  - OISST v2.1 Niño mensual (1982→)  sstoi.indices  (verificación cruzada y relleno
    de los meses recientes que ERSST aún no publica)

Salidas:
  - ml/data/raw/enso/*.txt                       texto crudo descargado
  - ml/data/processed/enso_monthly.parquet       un registro por mes
  - ml/data/processed/enso_yearly.parquet        un registro por año
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import httpx

from ml.config import DATA_PROCESSED, DATA_RAW

BASE = "https://www.cpc.ncep.noaa.gov/data/indices/"
SOURCES = {
    "oni": "oni.ascii.txt",
    "ersst": "ersst5.nino.mth.91-20.ascii",
    "oisst": "sstoi.indices",
}
RAW_DIR = DATA_RAW / "enso"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; enso-etl/1.0)"}

# Trimestre móvil -> mes central
SEAS_MID = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
            "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
MID_SEAS = {v: k for k, v in SEAS_MID.items()}

THRESH = 0.5         # umbral ONI de CPC
MIN_SEASONS = 5      # temporadas consecutivas superpuestas
MIN_CORE_MONTHS = 3  # además del año principal, otro año se marca si tiene ≥3 meses Ene–Jun en el evento
STRENGTH_BINS = [(2.0, "very_strong"), (1.5, "strong"), (1.0, "moderate"), (0.5, "weak")]


# ---------------------------------------------------------------- descarga
def download(client: httpx.Client, name: str) -> str:
    fname = SOURCES[name]
    r = client.get(BASE + fname)
    r.raise_for_status()
    txt = r.text
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / fname).write_text(txt)
    return txt


def _num(s: str) -> float:
    v = float(s)
    return np.nan if v <= -99 or v >= 999 else v  # -99.9, -99.99, 999.9 ...


# ---------------------------------------------------------------- parseo
def parse_oni(txt: str) -> pd.DataFrame:
    rows = []
    for line in txt.splitlines():
        p = line.split()
        if len(p) != 4 or p[0] not in SEAS_MID:
            continue
        rows.append({"month_date": pd.Timestamp(int(p[1]), SEAS_MID[p[0]], 1),
                     "oni": _num(p[3])})
    return pd.DataFrame(rows)


def parse_nino_table(txt: str) -> pd.DataFrame:
    """YR MON NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM (ERSST y OISST)."""
    rows = []
    for line in txt.splitlines():
        p = line.split()
        if len(p) != 10 or not p[0].isdigit():
            continue
        rows.append({"month_date": pd.Timestamp(int(p[0]), int(p[1]), 1),
                     "nino12_anom": _num(p[3]), "nino34_anom": _num(p[9])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- mensual
def build_monthly(oni: pd.DataFrame, ersst: pd.DataFrame, oisst: pd.DataFrame) -> pd.DataFrame:
    start = pd.Timestamp(1950, 1, 1)
    end = max(oni.month_date.max(), ersst.month_date.max(), oisst.month_date.max())
    df = pd.DataFrame({"month_date": pd.date_range(start, end, freq="MS")})
    df = df.merge(oni, on="month_date", how="left")
    df = df.merge(ersst, on="month_date", how="left")
    df = df.merge(oisst.rename(columns={"nino12_anom": "nino12_anom_oisst",
                                        "nino34_anom": "nino34_anom_oisst"}),
                  on="month_date", how="left")
    # Fuente de Niño: ERSST; sólo después del último mes de ERSST se rellena con OISST.
    last_ersst = ersst.dropna(subset=["nino12_anom"]).month_date.max()
    tail = (df.month_date > last_ersst) & df.nino12_anom.isna()
    df["nino_source"] = np.where(df.nino12_anom.notna(), "ersst", None)
    df.loc[tail, "nino12_anom"] = df.loc[tail, "nino12_anom_oisst"]
    df.loc[tail, "nino34_anom"] = df.loc[tail, "nino34_anom_oisst"]
    df.loc[tail & df.nino12_anom.notna(), "nino_source"] = "oisst"
    return df


# ---------------------------------------------------------------- eventos
def find_events(oni: pd.Series, dates: pd.Series) -> list[dict]:
    """Runs de ≥5 temporadas con ONI ≥ +0.5 (Niño) o ≤ −0.5 (Niña)."""
    events = []
    for kind, mask in (("nino", oni >= THRESH), ("nina", oni <= -THRESH)):
        m = mask.fillna(False).to_numpy()
        i = 0
        while i < len(m):
            if not m[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            if j - i + 1 >= MIN_SEASONS:
                seg = oni.iloc[i:j + 1]
                peak = seg.max() if kind == "nino" else seg.min()
                events.append({"kind": kind, "start": dates.iloc[i], "end": dates.iloc[j],
                               "peak_oni": float(peak),
                               "peak_date": dates.iloc[seg.abs().to_numpy().argmax() + i],
                               "ongoing": j == len(m) - 1,
                               "months": set(dates.iloc[i:j + 1])})
            i = j + 1
    return sorted(events, key=lambda e: e["start"])


def strength(peak: float) -> str | None:
    a = abs(peak)
    for thr, name in STRENGTH_BINS:
        if a >= thr:
            return name
    return None


def build_yearly(monthly: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    m = monthly.copy()
    m["year"] = m.month_date.dt.year
    m["mon"] = m.month_date.dt.month
    jj = m[m.mon <= 6].groupby("year")
    yearly = pd.DataFrame({
        "oni_jan_jun": jj.oni.mean(),
        "nino12_jan_jun": jj.nino12_anom.mean(),
        "nino34_jan_jun": jj.nino34_anom.mean(),
        "n_jan_jun_oni": jj.oni.count(),
    })
    yearly["oni_djf"] = m[m.mon == 1].set_index("year").oni  # DJF centrado en enero
    yearly = yearly.reset_index()

    oni_valid = monthly.dropna(subset=["oni"]).reset_index(drop=True)
    events = find_events(oni_valid.oni, oni_valid.month_date)

    yearly["enso_class"] = "neutral"
    yearly["enso_peak_oni"] = np.nan
    yearly["nino_strength"] = None
    yearly["event_start"] = pd.NaT
    yearly["event_end"] = pd.NaT
    best_cov = pd.Series(0, index=yearly.index)
    for ev in events:
        ev["years"] = []
        cov_by_year = {}
        for idx, y in yearly.year.items():
            core = {pd.Timestamp(y, k, 1) for k in range(1, 7)}
            cov_by_year[idx] = len(core & ev["months"])
        max_cov = max(cov_by_year.values())
        # Evento en curso que aún no alcanzó su núcleo Ene–Jun: no se asigna todavía.
        if max_cov == 0 or (ev["ongoing"] and max_cov < MIN_CORE_MONTHS):
            continue
        # Año principal: mayor cobertura Ene–Jun (empate -> el año más tardío, que contiene DJF).
        main_idx = max((i for i, c in cov_by_year.items() if c == max_cov),
                       key=lambda i: yearly.year[i])
        for idx, cov in cov_by_year.items():
            if not (idx == main_idx or cov >= MIN_CORE_MONTHS):
                continue
            y = yearly.year[idx]
            if cov > best_cov[idx]:
                best_cov[idx] = cov
                yearly.loc[idx, ["enso_class", "enso_peak_oni", "event_start", "event_end"]] = [
                    ev["kind"], ev["peak_oni"], ev["start"], ev["end"]]
                yearly.loc[idx, "nino_strength"] = strength(ev["peak_oni"]) if ev["kind"] == "nino" else None
                ev["years"].append(int(y))
    # Años sin Ene–Jun completo de ONI no se pueden clasificar con seguridad
    incomplete = yearly.n_jan_jun_oni < 6
    yearly.loc[incomplete & (yearly.enso_class == "neutral"), "enso_class"] = None
    yearly = yearly.drop(columns="n_jan_jun_oni")
    return yearly, events


# ---------------------------------------------------------------- main
def _fmt(d: pd.Timestamp) -> str:
    return f"{MID_SEAS[d.month]}-{d.year}"


def main() -> None:
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as client:
        txt = {k: download(client, k) for k in SOURCES}
    oni = parse_oni(txt["oni"])
    ersst = parse_nino_table(txt["ersst"])
    oisst = parse_nino_table(txt["oisst"])

    monthly = build_monthly(oni, ersst, oisst)
    yearly, events = build_yearly(monthly)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(DATA_PROCESSED / "enso_monthly.parquet", index=False)
    yearly.to_parquet(DATA_PROCESSED / "enso_yearly.parquet", index=False)

    # ---------- resumen
    print(f"Mensual: {len(monthly)} filas  {monthly.month_date.min():%Y-%m} → {monthly.month_date.max():%Y-%m}")
    print(f"Anual:   {len(yearly)} filas  {yearly.year.min()} → {yearly.year.max()}")
    lo = oni.dropna().iloc[-1]
    print(f"Último ONI: {_fmt(lo.month_date)} = {lo.oni:+.2f}")
    le = ersst.dropna().iloc[-1]
    print(f"Último ERSST: {le.month_date:%Y-%m}  Niño1+2 {le.nino12_anom:+.2f}  Niño3.4 {le.nino34_anom:+.2f}")
    lr = oisst.dropna().iloc[-1]
    print(f"Último OISST: {lr.month_date:%Y-%m}  Niño1+2 {lr.nino12_anom:+.2f}  Niño3.4 {lr.nino34_anom:+.2f}")

    both = monthly.dropna(subset=["nino12_anom_oisst"]).query("nino_source == 'ersst'")
    if len(both):
        for c in ("nino12", "nino34"):
            d = both[f"{c}_anom"] - both[f"{c}_anom_oisst"]
            r = both[f"{c}_anom"].corr(both[f"{c}_anom_oisst"])
            print(f"Cruce ERSST vs OISST {c} ({len(both)} meses): r={r:.3f}  "
                  f"sesgo medio={d.mean():+.2f}  MAE={d.abs().mean():.2f}")

    print("\nEventos El Niño (ONI ≥ +0.5, ≥5 temporadas):")
    for ev in events:
        if ev["kind"] != "nino":
            continue
        yrs = ",".join(map(str, ev["years"])) or "-"
        flag = "  (en curso)" if ev["ongoing"] else ""
        print(f"  {_fmt(ev['start']):>8} → {_fmt(ev['end']):<8} pico {ev['peak_oni']:+.2f} "
              f"({_fmt(ev['peak_date'])}) {strength(ev['peak_oni']):<11} año(s) asignado(s): {yrs}{flag}")

    print("\nAños El Niño (yearly.enso_class == 'nino'):")
    ny = yearly[yearly.enso_class == "nino"]
    print("  " + ", ".join(f"{r.year}:{r.nino_strength}" for r in ny.itertuples()))
    counts = yearly.enso_class.value_counts(dropna=False).to_dict()
    print(f"Clases: {counts}")


if __name__ == "__main__":
    main()
