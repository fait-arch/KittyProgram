"""Clima diario por CANTÓN (GEE) para aplicar el modelo a los 126 cantones de Supabase.

Geometrías: FAO GAUL 2015 nivel 2, emparejadas por nombre (provincia + cantón) con la tabla
`areas` de Supabase (`ml/data/cantons_supabase.csv`, id = uuid de Supabase). Máscara < 900 m como
en las provincias; si el cantón no tiene tierra < 900 m se usa todo el cantón (`mask_fallback`).

Descarga (mismo formato que ml/etl/gee_daily.py, área = uuid del cantón):
    era5   1991–2025  (normal climática 1991–2020 + años recientes)
    gpm    1998–2025  (quantile mapping de la lluvia)
    modis  2000–2025  (verdor EVI)
y por cantón: WorldClim (temperatura de referencia), altitud/latitud y la superficie de cultivo
(ESA WorldCover cultivos + árboles, < 900 m) para repartir las hectáreas de la provincia.

    ml/.venv/bin/python -m ml.etl.cantons [--workers 8]
    → data/processed/climate_daily_cantons.parquet, canton_meta.parquet
"""
from __future__ import annotations

import argparse
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import ee
import pandas as pd

from ml import config
from ml.etl import areas as A
from ml.etl import gee_daily as G

CANTONS_CSV = config.ROOT / "data" / "cantons_supabase.csv"
RAW = config.DATA_RAW / "gee_cantons"
OUT_DAILY = config.DATA_PROCESSED / "climate_daily_cantons.parquet"
OUT_META = config.DATA_PROCESSED / "canton_meta.parquet"
YEARS = {"era5": (1991, config.YEAR_END), "gpm": (1998, config.YEAR_END), "modis": (2000, config.YEAR_END),
         "viirs": (2012, config.YEAR_END)}
WORLDCLIM = "WORLDCLIM/V1/MONTHLY"
log = logging.getLogger("cantons")


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore")
                  .decode().lower())


def canton_geometries() -> pd.DataFrame:
    """Tabla de Supabase + geometría GAUL (o None si no hay match)."""
    sb = pd.read_csv(CANTONS_CSV, dtype=str)
    fc = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME", "Ecuador"))
    rows = fc.reduceColumns(ee.Reducer.toList(3), ["ADM1_NAME", "ADM2_NAME", "ADM2_CODE"]).getInfo()["list"]
    g = pd.DataFrame(rows, columns=["prov", "name", "code"])
    g["k"], g["kn"] = g.prov.map(norm) + "|" + g.name.map(norm), g.name.map(norm)
    sb["k"], sb["kn"] = sb.province.map(norm) + "|" + sb.name.map(norm), sb.name.map(norm)
    by_k = dict(zip(g.k, g.code))
    by_name = g.groupby("kn").code.apply(list).to_dict()
    sb["gaul_code"] = [by_k.get(k) or (by_name[n][0] if len(by_name.get(n, [])) == 1 else None)
                       for k, n in zip(sb.k, sb.kn)]
    return sb.drop(columns=["k", "kn"])


def _geom(code):
    fc = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM2_CODE", int(float(code))))
    return fc.geometry(maxError=100).simplify(A.SIMPLIFY_M)


def canton_mask(geom) -> tuple[ee.Image, bool]:
    low = A.cacao_mask()
    n = low.reduceRegion(ee.Reducer.count(), geom, 1000, bestEffort=True).getInfo().get("cacao_land") or 0
    if n >= 5:
        return low, False
    return ee.Image.constant(1).selfMask().rename("cacao_land"), True


def static_meta(cid: str, geom, mask) -> dict:
    """WorldClim mensual, altitud, latitud y hectáreas de cultivo (WorldCover 40/10/20, < 900 m)."""
    wc = ee.ImageCollection(WORLDCLIM).toList(12)
    clim = {}
    for i in range(12):
        img = ee.Image(wc.get(i)).select(["tavg", "tmin", "tmax", "prec"])
        v = img.updateMask(mask).reduceRegion(ee.Reducer.mean(), geom, 1000, bestEffort=True).getInfo()
        clim[i + 1] = v
    elev = ee.Image(A.SRTM).select("elevation").updateMask(mask).reduceRegion(
        ee.Reducer.mean(), geom, 500, bestEffort=True).getInfo().get("elevation")
    cent = geom.centroid(100).coordinates().getInfo()
    lc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    crop = lc.eq(40).Or(lc.eq(10)).Or(lc.eq(20)).And(mask.unmask(0))
    ha = crop.multiply(ee.Image.pixelArea()).divide(1e4).reduceRegion(
        ee.Reducer.sum(), geom, 100, bestEffort=True, maxPixels=1e10).getInfo().get("Map") or 0.0
    return {"area_name": cid, "lon": cent[0], "lat": cent[1], "elev_m": elev, "crop_ha": ha, "worldclim": clim}


def run(workers: int = 8):
    A.init()
    cant = canton_geometries()
    cant.to_csv(config.DATA_PROCESSED / "canton_gaul_match.csv", index=False)
    ok = cant[cant.gaul_code.notna()]
    log.info("cantones con geometría: %d / %d", len(ok), len(cant))
    geoms = {r.id: _geom(r.gaul_code) for r in ok.itertuples()}
    masks = {}
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(canton_mask, g): cid for cid, g in geoms.items()}
        for f in as_completed(futs):
            masks[futs[f]] = f.result()
    # 1) estáticos
    meta_rows = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(G._with_retry, (lambda c=cid: static_meta(c, geoms[c], masks[c][0])), f"meta/{cid}"): cid
                for cid in geoms}
        for f in as_completed(futs):
            r = f.result()
            r["mask_fallback"] = masks[futs[f]][1]
            meta_rows.append(r)
    meta = pd.DataFrame(meta_rows).merge(cant, left_on="area_name", right_on="id", how="left")
    meta.to_pickle(config.DATA_PROCESSED / "canton_meta.pkl")
    # 2) clima diario (reutiliza el descargador de provincias con otra carpeta)
    G.RAW_DIR = RAW
    for ds, (y0, y1) in YEARS.items():
        tasks = [(ds, cid, geoms[cid], masks[cid][0], y) for cid in geoms for y in range(y0, y1 + 1)
                 if not G.chunk_path(ds, cid, y).exists()]
        log.info("== %s: %d trozos", ds, len(tasks))
        bad = 0
        with ThreadPoolExecutor(workers) as ex:
            futs = [ex.submit(G.fetch_chunk, *t) for t in tasks]
            for i, f in enumerate(as_completed(futs), 1):
                try:
                    f.result()
                except Exception as e:  # noqa: BLE001
                    bad += 1
                    log.error("FALLO %s", str(e)[:200])
                if i % 500 == 0:
                    log.info("%s %d/%d", ds, i, len(tasks))
        log.info("== %s terminado, fallos: %d", ds, bad)
    combine()


def combine() -> pd.DataFrame:
    frames = []
    for ds in YEARS:
        files = sorted((RAW / ds).glob("*.parquet"))
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        frames.append(df.drop(columns=[c for c in ("n_images",) if c in df.columns]))
    out = frames[0]
    for df in frames[1:]:
        out = out.merge(df, on=["date", "area_name"], how="left")
    # el slug del uuid quita guiones: se recupera el uuid original
    ids = pd.read_csv(CANTONS_CSV, dtype=str).id
    by_slug = {A.slug(i): i for i in ids}
    out["area_name"] = out.area_name.map(lambda s: by_slug.get(A.slug(s), s))
    out["rh_pct"] = G._rh(out.t2m_c, out.dewpoint_c).clip(upper=100)
    out = out.sort_values(["area_name", "date"]).reset_index(drop=True)
    out.to_parquet(OUT_DAILY, index=False)
    log.info("escrito %s: %d filas, %d cantones", OUT_DAILY, len(out), out.area_name.nunique())
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--combine-only", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    combine() if a.combine_only else run(a.workers)


if __name__ == "__main__":
    main()
