"""Area geometries for cacao provinces (FAO GAUL 2015 level 1, Ecuador).

Each area is a (geometry, mask) pair:
  - geometry: dissolved GAUL province polygon (lightly simplified, ~500 m tolerance)
  - mask: ee.Image (1 where cacao-relevant land, i.e. SRTM elevation < 900 m — ECOCROP
    ALTMX for Theobroma cacao — masked elsewhere)

'national' = union of the selected provinces, with the same elevation mask.

Usage with a reducer:
    geom, mask = get_areas()["Los Rios"]
    img.updateMask(mask).reduceRegion(ee.Reducer.mean(), geom, 9000, bestEffort=True)
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "BACK") not in sys.path:
    sys.path.insert(0, str(ROOT / "BACK"))

from ml import config  # noqa: E402

GAUL_L1 = "FAO/GAUL/2015/level1"
SRTM = "USGS/SRTMGL1_003"
MAX_ELEV_M = 900  # ECOCROP Theobroma cacao ALTMX
SIMPLIFY_M = 500
NATIONAL = "national"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _norm(name)).strip("_")


def init() -> None:
    from nasa_data import init_gee
    init_gee()


def gaul_names(provinces: list[str] | None = None) -> dict[str, str]:
    """Map config province names -> exact GAUL ADM1_NAME (case/accents-insensitive)."""
    provinces = provinces or config.PROVINCES
    fc = ee.FeatureCollection(GAUL_L1).filter(ee.Filter.eq("ADM0_NAME", "Ecuador"))
    available = fc.aggregate_array("ADM1_NAME").distinct().getInfo()
    lookup = {_norm(n): n for n in available}
    out = {}
    for p in provinces:
        if _norm(p) not in lookup:
            raise KeyError(f"Province {p!r} not found in GAUL; available: {sorted(available)}")
        out[p] = lookup[_norm(p)]
    return out


def cacao_mask() -> ee.Image:
    """1 where SRTM elevation < 900 m, masked otherwise."""
    elev = ee.Image(SRTM).select("elevation")
    return elev.lt(MAX_ELEV_M).selfMask().rename("cacao_land")


def get_areas(provinces: list[str] | None = None, include_national: bool = True
              ) -> dict[str, tuple[ee.Geometry, ee.Image]]:
    """Return {area_name: (geometry, mask_image)}; area_name is the exact GAUL name
    (plus 'national')."""
    names = gaul_names(provinces or config.ALL_PROVINCES)
    national_names = set(gaul_names(config.PROVINCES).values())    # 'national' = solo la Costa+Sucumbíos
    fc = ee.FeatureCollection(GAUL_L1).filter(ee.Filter.eq("ADM0_NAME", "Ecuador"))
    mask = cacao_mask()
    areas: dict[str, tuple[ee.Geometry, ee.Image]] = {}
    geoms = []
    for gname in names.values():
        g = fc.filter(ee.Filter.eq("ADM1_NAME", gname)).geometry(maxError=100).simplify(SIMPLIFY_M)
        areas[gname] = (g, mask)
        if gname in national_names:
            geoms.append(g)
    if include_national:
        nat = ee.FeatureCollection([ee.Feature(g) for g in geoms]).union(maxError=100).geometry()
        areas[NATIONAL] = (nat, mask)
    return areas


def area_stats(areas: dict | None = None) -> dict[str, dict]:
    """Total vs. masked (<900 m) area in km² per area (diagnostic)."""
    areas = areas or get_areas()
    out = {}
    px = ee.Image.pixelArea().divide(1e6)
    for name, (g, mask) in areas.items():
        tot = g.area(maxError=100).divide(1e6)
        msk = px.updateMask(mask).reduceRegion(ee.Reducer.sum(), g, 500, bestEffort=True,
                                              maxPixels=1e10).get("area")
        out[name] = ee.Dictionary({"total_km2": tot, "masked_km2": msk})
    res = ee.Dictionary(out).getInfo()
    return res


if __name__ == "__main__":
    init()
    print(gaul_names())
    for k, v in area_stats().items():
        print(f"{k:35s} total={v['total_km2']:9.0f} km2  <900m={v['masked_km2']:9.0f} km2")
