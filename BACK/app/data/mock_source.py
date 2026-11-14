"""Fuente de datos de PRUEBA (DATA_SOURCE=mock).

Misma interfaz que SupabaseSource. Catálogos copiados de las semillas reales (0005/0006);
territorio, clima, riesgo y pérdidas son SINTÉTICOS (deterministas) para que el frontend
pueda trabajar antes de que el ETL y el modelo llenen la BD. Nada de esto es un resultado.
"""
import calendar
import hashlib
import math
import uuid
from datetime import date
from typing import Any

from .common import name_key

NS = uuid.UUID("6b1f3c1e-7a51-4d1e-9a2b-000000000000")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def _rand(*parts: Any) -> float:
    """Número determinista en [0, 1) a partir de una clave."""
    h = hashlib.sha256("/".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


# ── Catálogos (semillas reales de la BD) ───────────────────────────────
SCENARIOS = [
    {"id": "normal", "name_es": "Año normal (neutro)", "kind": "historical", "phase": 1, "period_start": 2001, "period_end": 2025, "ssp": None, "description": "Promedio de años ENSO neutros."},
    {"id": "nino", "name_es": "Año Niño", "kind": "historical", "phase": 1, "period_start": 2001, "period_end": 2025, "ssp": None, "description": "Promedio de años con El Niño (ONI ≥ 0.5 o Niño costero)."},
    {"id": "nina", "name_es": "Año Niña", "kind": "historical", "phase": 1, "period_start": 2001, "period_end": 2025, "ssp": None, "description": "Promedio de años con La Niña."},
    {"id": "actual", "name_es": "Temporada en curso", "kind": "current", "phase": 1, "period_start": 2026, "period_end": 2027, "ssp": None, "description": "Condiciones ENSO actuales según NOAA CPC."},
    {"id": "ssp245_2050", "name_es": "2050 — emisiones moderadas", "kind": "projection", "phase": 2, "period_start": 2041, "period_end": 2060, "ssp": "ssp245", "description": "NEX-GDDP-CMIP6, 4 modelos, método delta."},
    {"id": "ssp585_2050", "name_es": "2050 — emisiones altas", "kind": "projection", "phase": 2, "period_start": 2041, "period_end": 2060, "ssp": "ssp585", "description": "NEX-GDDP-CMIP6, 4 modelos, método delta."},
]

CROPS = [{"id": "cacao", "name_es": "Cacao", "scientific_name": "Theobroma cacao", "family": "Malvaceae",
          "crop_type": "perennial", "region": ["costa", "amazonia"], "is_perennial": True}]

REQUIREMENTS = [
    {"crop_id": "cacao", "parameter": "temp_mean", "opt_min": 21, "opt_max": 32, "abs_min": 10, "abs_max": 38, "value_text": None, "unit": "°C"},
    {"crop_id": "cacao", "parameter": "rain_annual", "opt_min": 1200, "opt_max": 3000, "abs_min": 900, "abs_max": 7600, "value_text": None, "unit": "mm/año"},
    {"crop_id": "cacao", "parameter": "ph", "opt_min": 5.0, "opt_max": 6.5, "abs_min": None, "abs_max": None, "value_text": None, "unit": "pH"},
    {"crop_id": "cacao", "parameter": "altitude", "opt_min": None, "opt_max": 900, "abs_min": None, "abs_max": None, "value_text": None, "unit": "m"},
    {"crop_id": "cacao", "parameter": "killing_temp", "opt_min": None, "opt_max": None, "abs_min": 0, "abs_max": None, "value_text": None, "unit": "°C"},
    {"crop_id": "cacao", "parameter": "growth_days", "opt_min": 180, "opt_max": 365, "abs_min": None, "abs_max": None, "value_text": None, "unit": "días"},
    {"crop_id": "cacao", "parameter": "light", "opt_min": None, "opt_max": None, "abs_min": None, "abs_max": None, "value_text": "cielo despejado a sombra ligera", "unit": None},
    {"crop_id": "cacao", "parameter": "soil_depth", "opt_min": None, "opt_max": None, "abs_min": None, "abs_max": None, "value_text": "profundo (>150 cm)", "unit": None},
    {"crop_id": "cacao", "parameter": "soil_texture", "opt_min": None, "opt_max": None, "abs_min": None, "abs_max": None, "value_text": "pesado, orgánico", "unit": None},
    {"crop_id": "cacao", "parameter": "drainage", "opt_min": None, "opt_max": None, "abs_min": None, "abs_max": None, "value_text": "bien drenado (tolera periodos secos)", "unit": None},
]


def _thr(p, v, mn, mx, unit):
    return {"pathogen_id": p, "variable_id": v, "min_value": mn, "max_value": mx, "unit": unit,
            "validated": False, "resolution": "daily", "source_ref": "literatura — por validar"}


PATHOGENS = [
    {"id": "monilia", "name_es": "Moniliasis", "scientific_name": "Moniliophthora roreri", "crop_id": "cacao",
     "organ_affected": "mazorca", "spread_by": ["viento", "lluvia"],
     "description": "Pudrición helada de la mazorca; favorecida por humedad alta sostenida.",
     "disease_thresholds": [_thr("monilia", "rh_mean", 80, None, "%"), _thr("monilia", "t2m", 20, 28, "°C")]},
    {"id": "phytophthora", "name_es": "Mazorca negra", "scientific_name": "Phytophthora spp.", "crop_id": "cacao",
     "organ_affected": "mazorca", "spread_by": ["lluvia", "salpique"],
     "description": "Pudrición negra; favorecida por lluvia y mazorcas mojadas.",
     "disease_thresholds": [_thr("phytophthora", "precip", 1, None, "mm/día"), _thr("phytophthora", "rh_mean", 85, None, "%"),
                            _thr("phytophthora", "t2m", 20, 30, "°C")]},
    {"id": "escoba_bruja", "name_es": "Escoba de bruja", "scientific_name": "Moniliophthora perniciosa", "crop_id": "cacao",
     "organ_affected": "brotes", "spread_by": ["viento", "lluvia"],
     "description": "Deforma brotes y cojines florales; favorecida por humedad.",
     "disease_thresholds": [_thr("escoba_bruja", "rh_mean", 80, None, "%"), _thr("escoba_bruja", "t2m", 20, 30, "°C")]},
]

PHENOLOGY = [
    {"crop_id": "cacao", "region": "costa", "stage": "floracion", "months": [12, 1, 2], "is_risk_window": False},
    {"crop_id": "cacao", "region": "costa", "stage": "desarrollo_mazorca", "months": [1, 2, 3, 4, 5, 6], "is_risk_window": True},
    {"crop_id": "cacao", "region": "costa", "stage": "cosecha_principal", "months": [3, 4, 5, 6, 7], "is_risk_window": False},
    {"crop_id": "cacao", "region": "costa", "stage": "cosecha_secundaria", "months": [10, 11, 12], "is_risk_window": False},
    {"crop_id": "cacao", "region": "amazonia", "stage": "desarrollo_mazorca", "months": list(range(1, 13)), "is_risk_window": True},
]

STRATEGIES = [
    {"id": "actual", "name_es": "Manejo actual", "description": "Línea base: sin cambios en el manejo.", "cost_usd_ha_year": None, "applies_to_zones": ["segura", "manejo", "transicion", "critica"], "evidence": None, "source_ref": None, "validated": False},
    {"id": "sanitario", "name_es": "Manejo sanitario", "description": "Cosecha sanitaria semanal, poda y retiro de mazorcas enfermas.", "cost_usd_ha_year": None, "applies_to_zones": ["manejo", "critica"], "evidence": "Completar con literatura / INIAP", "source_ref": None, "validated": False},
    {"id": "drenaje_sombra", "name_es": "Drenaje + sombra regulada", "description": "Canales de drenaje y ajuste de sombra en sistema agroforestal.", "cost_usd_ha_year": None, "applies_to_zones": ["manejo", "transicion"], "evidence": "Completar con literatura / INIAP", "source_ref": None, "validated": False},
    {"id": "diversificacion", "name_es": "Diversificación", "description": "Cacao con plátano y maderables; rotación de cultivos intercalados en cacao joven.", "cost_usd_ha_year": None, "applies_to_zones": ["transicion", "critica"], "evidence": "Completar con literatura / INIAP", "source_ref": None, "validated": False},
]

STRATEGY_EFFECTS = [
    {"strategy_id": s, "target": t, "reduction_pct_low": None, "reduction_pct_high": None, "validated": False, "notes": "Completar con literatura / INIAP"}
    for s, t in [("sanitario", "monilia"), ("sanitario", "phytophthora"), ("sanitario", "escoba_bruja"),
                 ("drenaje_sombra", "phytophthora"), ("drenaje_sombra", "encharcamiento"), ("drenaje_sombra", "calor"),
                 ("diversificacion", "ingreso")]
]

SOURCES = [
    {"id": "gpm_imerg", "name": "GPM IMERG Monthly v07", "provider": "NASA", "spatial_res_m": 11000, "url": "https://gpm.nasa.gov/data/imerg"},
    {"id": "smap_l4", "name": "SMAP L4 Soil Moisture", "provider": "NASA", "spatial_res_m": 11000, "url": "https://smap.jpl.nasa.gov"},
    {"id": "modis_ndvi", "name": "MODIS Terra NDVI (MOD13Q1)", "provider": "NASA", "spatial_res_m": 250, "url": "https://lpdaac.usgs.gov/products/mod13q1v061/"},
    {"id": "srtm", "name": "SRTM 30 m", "provider": "NASA", "spatial_res_m": 30, "url": "https://www.earthdata.nasa.gov/sensors/srtm"},
    {"id": "nasa_power", "name": "NASA POWER Agroclimatology", "provider": "NASA", "spatial_res_m": 55000, "url": "https://power.larc.nasa.gov"},
    {"id": "era5_land", "name": "ERA5-Land (diario y mensual)", "provider": "ECMWF/Copernicus", "spatial_res_m": 9000, "url": "https://cds.climate.copernicus.eu"},
    {"id": "gddp_cmip6", "name": "NEX-GDDP-CMIP6", "provider": "NASA", "spatial_res_m": 27000, "url": "https://www.nccs.nasa.gov"},
    {"id": "noaa_cpc", "name": "NOAA CPC ENSO indices (ONI, Niño 1+2)", "provider": "NOAA", "spatial_res_m": None, "url": "https://www.cpc.ncep.noaa.gov/data/indices/"},
    {"id": "espac", "name": "ESPAC — INEC", "provider": "INEC", "spatial_res_m": None, "url": "https://www.ecuadorencifras.gob.ec/estadisticas-agropecuarias-2/"},
]

VARIABLES = [
    {"id": "t2m", "name": "Temperatura del aire media", "unit": "°C", "source_id": "era5_land", "description": "Temperatura promedio a 2 m del suelo."},
    {"id": "rh_mean", "name": "Humedad relativa media diaria", "unit": "%", "source_id": "era5_land", "description": "Calculada con temperatura y punto de rocío de ERA5-Land."},
    {"id": "precip", "name": "Lluvia mensual", "unit": "mm/mes", "source_id": "gpm_imerg", "description": "Cuánta agua cae del cielo cada mes."},
    {"id": "heavy_rain_days", "name": "Días de lluvia intensa (>50 mm)", "unit": "días/mes", "source_id": "gpm_imerg", "description": "Días con aguaceros que pueden causar erosión o inundación."},
    {"id": "saturated_days", "name": "Días con suelo saturado", "unit": "días/mes", "source_id": "smap_l4", "description": "Días con humedad superficial muy alta: riesgo de asfixia de raíces."},
    {"id": "ndvi", "name": "Verdor de la vegetación (NDVI)", "unit": "índice", "source_id": "modis_ndvi", "description": "Qué tan verde y activa está la vegetación."},
]

# ── Territorio sintético: cantones cacaoteros (centroides aproximados) ──
CANTONS = [
    ("Los Rios", "Vinces", -1.55, -79.75), ("Los Rios", "Quevedo", -1.02, -79.46),
    ("Los Rios", "Babahoyo", -1.80, -79.53), ("Los Rios", "Ventanas", -1.45, -79.46),
    ("Los Rios", "Baba", -1.78, -79.67), ("Guayas", "Milagro", -2.13, -79.59),
    ("Guayas", "Naranjal", -2.67, -79.62), ("Guayas", "El Empalme", -1.05, -79.63),
    ("Manabi", "Chone", -0.70, -80.10), ("Manabi", "Flavio Alfaro", -0.40, -79.90),
    ("Esmeraldas", "Quininde", 0.33, -79.47), ("Esmeraldas", "Esmeraldas", 0.95, -79.65),
    ("El Oro", "Machala", -3.26, -79.96), ("El Oro", "Pasaje", -3.33, -79.81),
]
HALF = 0.07  # medio lado del cuadrado de prueba (grados)

WET = [0.75, 0.9, 1.0, 0.95, 0.7, 0.45, 0.25, 0.15, 0.12, 0.15, 0.25, 0.5]          # ene..dic
PRECIP_BASE = [300, 380, 400, 300, 150, 60, 20, 10, 15, 20, 30, 120]               # mm/mes
SCEN_RISK = {"normal": 0.72, "nino": 1.0, "nina": 0.6, "actual": 1.05, "ssp245_2050": 1.1, "ssp585_2050": 1.2}
SCEN_RAIN = {"normal": 0.8, "nino": 1.6, "nina": 0.7, "actual": 1.7, "ssp245_2050": 1.0, "ssp585_2050": 1.1}
SCEN_TEMP = {"normal": 0.0, "nino": 0.5, "nina": -0.3, "actual": 0.6, "ssp245_2050": 1.6, "ssp585_2050": 2.4}
SCEN_LOSS = {"normal": (2, 6), "nino": (14, 20), "nina": (1, 5), "actual": (16, 22), "ssp245_2050": (18, 22), "ssp585_2050": (22, 26)}
PATH_MULT = {"monilia": 0.95, "phytophthora": 0.8, "escoba_bruja": 0.65}
PRICE_USD_T = 5000.0  # sintético
YIELD_T_HA = 0.60     # sintético


def _square(lat: float, lon: float, h: float) -> dict:
    ring = [[lon - h, lat - h], [lon + h, lat - h], [lon + h, lat + h], [lon - h, lat + h], [lon - h, lat - h]]
    return {"type": "MultiPolygon", "coordinates": [[ring]]}


def _build_areas() -> list[dict]:
    areas: list[dict] = []
    provinces: dict[str, list[tuple[float, float]]] = {}
    for prov, _, lat, lon in CANTONS:
        provinces.setdefault(prov, []).append((lat, lon))
    for prov, pts in provinces.items():
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        ring = [[min(lons) - 0.15, min(lats) - 0.15], [max(lons) + 0.15, min(lats) - 0.15],
                [max(lons) + 0.15, max(lats) + 0.15], [min(lons) - 0.15, max(lats) + 0.15],
                [min(lons) - 0.15, min(lats) - 0.15]]
        areas.append({"id": _id("prov", prov), "name": prov, "kind": "province", "parent_id": None,
                      "region": "costa", "inec_dpa_code": None, "name_key": name_key(prov),
                      "area_ha": round(abs((max(lons) - min(lons) + 0.3) * (max(lats) - min(lats) + 0.3)) * 1.23e6),
                      "geom": {"type": "MultiPolygon", "coordinates": [[ring]]},
                      "centroid": {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons)}})
    for prov, name, lat, lon in CANTONS:
        areas.append({"id": _id("canton", prov, name), "name": name, "kind": "canton", "parent_id": _id("prov", prov),
                      "region": "costa", "inec_dpa_code": None, "name_key": name_key(name),
                      "area_ha": round((2 * HALF) ** 2 * 1.23e6), "geom": _square(lat, lon, HALF),
                      "centroid": {"lat": lat, "lon": lon}})
    return areas


def _months_between(date_from: str | None, date_to: str | None, default_from="2015-01-01", default_to="2025-12-01"):
    y0, m0 = map(int, (date_from or default_from)[:7].split("-"))
    y1, m1 = map(int, (date_to or default_to)[:7].split("-"))
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


NINO_YEARS = {2015: 1.2, 2016: 1.6, 2023: 1.4, 2024: 1.3}
NINA_YEARS = {2021: 0.8, 2022: 0.75}


class MockSource:
    name = "mock"

    def __init__(self) -> None:
        self._areas = _build_areas()
        self._by_id = {a["id"]: a for a in self._areas}

    def ping(self) -> bool:
        return True

    # ── catálogos ─────────────────────────────────────
    def scenarios(self):
        return SCENARIOS

    def crops(self):
        return CROPS

    def crop_requirements(self, crop):
        return [r for r in REQUIREMENTS if r["crop_id"] == crop]

    def pathogens(self, crop):
        return [p for p in PATHOGENS if p["crop_id"] == crop]

    def phenology(self, crop):
        return [p for p in PHENOLOGY if p["crop_id"] == crop]

    def strategies(self):
        return STRATEGIES

    def strategy_effects(self):
        return STRATEGY_EFFECTS

    def sources(self):
        return SOURCES

    def variables(self):
        return VARIABLES

    def active_model(self, crop):
        if crop != "cacao":
            return None
        return {"id": _id("model", "mock"), "name": "mock_cacao_loss", "crop_id": "cacao", "algorithm": "mock",
                "target": "yield_anomaly_pct", "features": ["fav_days_monilia", "fav_days_phytophthora", "heavy_rain_days",
                                                            "saturated_days", "nino12_anom_jan_jun", "oni_jan_jun", "suitability_now"],
                "metrics": {"mae": None, "note": "Datos sintéticos: no hay modelo entrenado."},
                "train_start_year": None, "train_end_year": None, "n_samples": 0, "is_active": True,
                "created_at": "2026-11-14T00:00:00Z"}

    def latest_price(self, crop):
        return {"price_usd_t": PRICE_USD_T, "months": 12, "last_month": "2026-10-01"}

    # ── ENSO ──────────────────────────────────────────
    def _oni(self, y: int, m: int) -> float:
        if (y, m) >= (2026, 5):   # Niño 2026 en curso: sube hasta ONI 2.46 (ASO)
            return round(min(2.46, 0.6 + 0.45 * ((y - 2026) * 12 + m - 5)), 2)
        if y == 2026:
            return round(-0.2 + 0.15 * m, 2)
        base = NINO_YEARS.get(y, NINA_YEARS.get(y, 0.0))
        if base > 1:
            return round((base - 1) * 4 * math.sin(math.pi * m / 12) + 0.5, 2)
        if base and base < 1:
            return round(-0.9 * math.sin(math.pi * m / 12) - 0.3, 2)
        return round((_rand("oni", y, m) - 0.5) * 0.8, 2)

    def _phase(self, idx: str, v: float) -> str:
        t = 0.5 if idx == "oni" else 0.4
        return "nino" if v >= t else "nina" if v <= -t else "neutral"

    def enso_index(self, index_ids, date_from, date_to):
        rows = []
        for y, m in _months_between(date_from, date_to, "1990-01-01", "2026-10-01"):
            if (y, m) > (2026, 10):
                break
            oni = self._oni(y, m)
            if "oni" in index_ids and (y, m) <= (2026, 9):
                rows.append({"index_id": "oni", "month_date": f"{y}-{m:02d}-01", "value": oni, "phase": self._phase("oni", oni)})
            if "nino12_anom" in index_ids:
                v = 5.25 if (y, m) == (2026, 10) else round(oni * 1.6 + (_rand("n12", y, m) - 0.5) * 0.4, 2)
                rows.append({"index_id": "nino12_anom", "month_date": f"{y}-{m:02d}-01", "value": v, "phase": self._phase("nino12_anom", v)})
        return rows

    def enso_latest(self, index_id):
        if index_id == "oni":
            return {"index_id": "oni", "month_date": "2026-09-01", "value": 2.46, "phase": "nino", "fetched_at": None}
        if index_id == "nino12_anom":
            return {"index_id": "nino12_anom", "month_date": "2026-10-01", "value": 5.25, "phase": "nino", "fetched_at": None}
        return None

    def enso_events(self):
        return [
            {"id": "nino_1997_98", "phase": "nino", "start_month": "1997-05-01", "end_month": "1998-05-01", "peak_oni": 2.4, "peak_nino12": 4.1, "intensity": "muy_fuerte", "is_coastal": False},
            {"id": "nino_2015_16", "phase": "nino", "start_month": "2015-03-01", "end_month": "2016-05-01", "peak_oni": 2.6, "peak_nino12": 2.9, "intensity": "muy_fuerte", "is_coastal": False},
            {"id": "nino_costero_2017", "phase": "nino", "start_month": "2017-01-01", "end_month": "2017-05-01", "peak_oni": 0.1, "peak_nino12": 2.5, "intensity": "fuerte", "is_coastal": True},
            {"id": "nino_2023_24", "phase": "nino", "start_month": "2023-05-01", "end_month": "2024-05-01", "peak_oni": 2.0, "peak_nino12": 3.0, "intensity": "fuerte", "is_coastal": False},
            {"id": "nino_2026_27", "phase": "nino", "start_month": "2026-05-01", "end_month": None, "peak_oni": 2.46, "peak_nino12": 5.25, "intensity": "muy_fuerte", "is_coastal": False},
        ]

    def enso_years(self):
        out = []
        for y in range(1990, 2027):
            vals = [self._oni(y, m) for m in range(1, 7)]
            oni = round(sum(vals) / 6, 2)
            cls = "nino" if oni >= 0.5 else "nina" if oni <= -0.5 else "neutral"
            out.append({"year": y, "oni_jan_jun": oni, "nino12_anom_jan_jun": round(oni * 1.6, 2), "enso_class": cls, "is_coastal_nino": False})
        return out

    # ── territorio ────────────────────────────────────
    @staticmethod
    def _plain(a: dict) -> dict:
        return {k: a[k] for k in ("id", "name", "kind", "parent_id", "area_ha", "region", "inec_dpa_code", "name_key")}

    def areas(self, kind=None, parent_id=None):
        return [self._plain(a) for a in self._areas
                if (not kind or a["kind"] == kind) and (not parent_id or a["parent_id"] == parent_id)]

    def area(self, area_id):
        a = self._by_id.get(area_id)
        return self._plain(a) if a else None

    def find_area(self, kind, name):
        k = name_key(name)
        return next((self._plain(a) for a in self._areas if a["kind"] == kind and a["name_key"] == k), None)

    def areas_geom(self, kind, parent_id=None):
        return [{"id": a["id"], "name": a["name"], "kind": a["kind"], "parent_id": a["parent_id"],
                 "region": a["region"], "geom": a["geom"]}
                for a in self._areas if a["kind"] == kind and (not parent_id or a["parent_id"] == parent_id)]

    def _h(self, area_id: str) -> float:
        return 0.8 + 0.4 * _rand("hum", area_id)

    def static_features(self, area_id):
        if area_id not in self._by_id:
            return None
        return {"area_id": area_id, "elevation_mean_m": round(10 + 250 * _rand("elev", area_id)),
                "slope_mean_deg": round(0.5 + 6 * _rand("slope", area_id), 1),
                "soil_ph": round(5.3 + 1.3 * _rand("ph", area_id), 1),
                "soil_organic_c_gkg": round(8 + 15 * _rand("oc", area_id), 1),
                "clay_pct": round(20 + 25 * _rand("clay", area_id)), "sand_pct": round(15 + 30 * _rand("sand", area_id)),
                "land_cover": {"tree": round(0.3 + 0.3 * _rand("tree", area_id), 2), "cropland": round(0.2 + 0.3 * _rand("crop", area_id), 2)}}

    def _exposed(self, area_id: str) -> float:
        a = self._by_id[area_id]
        if a["kind"] == "canton":
            return float(round(3000 + 17000 * _rand("ha", area_id), -2))
        return sum(self._exposed(c["id"]) for c in self._areas if c["parent_id"] == area_id)

    def exposure(self, crop, area_id=None):
        ids = [area_id] if area_id else [a["id"] for a in self._areas]
        return [{"area_id": i, "crop_id": crop, "ref_year": 2024, "crop_ha": self._exposed(i), "method": "manual"}
                for i in ids if i in self._by_id and crop == "cacao"]

    # ── clima y riesgo ────────────────────────────────
    def _climate_month(self, area_id: str, scenario: str, m: int) -> dict:
        h = self._h(area_id)
        elev = self.static_features(area_id)["elevation_mean_m"]
        t = 25.8 - elev * 0.0055 + (1.0 if m in (3, 4) else -1.4 if m in (7, 8, 9) else 0) + SCEN_TEMP[scenario]
        p = PRECIP_BASE[m - 1] * SCEN_RAIN[scenario] * h
        rh = min(97, 76 + 16 * WET[m - 1] * min(1.2, SCEN_RISK[scenario]))
        return {"t2m": round(t, 1), "precip": round(p, 1), "rh_mean": round(rh, 1),
                "heavy_rain_days": round(max(0, p / 110 - 0.5), 1), "wet_days": round(min(calendar.monthrange(2025, m)[1], p / 14), 1),
                "saturated_days": round(max(0, (p - 200) / 25), 1)}

    def scenario_climate(self, area_id, scenario, variables=None):
        if area_id not in self._by_id or scenario not in SCEN_RISK:
            return []
        rows = []
        for m in range(1, 13):
            vals = self._climate_month(area_id, scenario, m)
            for v, val in vals.items():
                if variables and v not in variables:
                    continue
                rows.append({"area_id": area_id, "scenario_id": scenario, "variable_id": v, "month": m,
                             "value_mean": val, "value_min": round(val * 0.75, 1), "value_max": round(val * 1.3, 1),
                             "n_members": 6, "method": "delta" if scenario.startswith("ssp") else "composite"})
        return rows

    def monthly_series(self, area_id, variables, date_from, date_to):
        if area_id not in self._by_id:
            return []
        rows = []
        for y, m in _months_between(date_from, date_to):
            boost = NINO_YEARS.get(y, NINA_YEARS.get(y, 1.0))
            scen = "nino" if boost > 1 else "nina" if boost < 1 else "normal"
            clim = self._climate_month(area_id, scen, m)
            base = self._climate_month(area_id, "normal", m)
            vals = {**clim, "ndvi": round(0.78 - 0.08 * (boost - 1) - 0.05 * (1 - WET[m - 1]) + (_rand("ndvi", area_id, y, m) - 0.5) * 0.04, 3)}
            for v in variables:
                if v in vals:
                    anom = round(vals[v] - base.get(v, vals[v]), 2) if v in base else None
                    rows.append({"variable_id": v, "month_date": f"{y}-{m:02d}-01", "value": vals[v], "anomaly": anom})
        return rows

    def monthly_hazard(self, area_id, date_from, date_to):
        if area_id not in self._by_id:
            return []
        rows = []
        for y, m in _months_between(date_from, date_to):
            boost = NINO_YEARS.get(y, NINA_YEARS.get(y, 1.0))
            scen = "nino" if boost > 1 else "nina" if boost < 1 else "normal"
            c = self._climate_month(area_id, scen, m)
            rows.append({"area_id": area_id, "month_date": f"{y}-{m:02d}-01", "precip_total_mm": c["precip"],
                         "wet_days": round(c["wet_days"]), "heavy_rain_days": round(c["heavy_rain_days"]),
                         "max_consecutive_wet_days": round(c["wet_days"] * 0.5), "rh_mean": c["rh_mean"],
                         "humid_days": round(min(30, max(0, (c["rh_mean"] - 70) * 1.5))), "t2m_mean": c["t2m"],
                         "hot_days": 0, "saturated_days": round(c["saturated_days"]),
                         "n_days_with_data": calendar.monthrange(y, m)[1]})
        return rows

    def _risk(self, area_id: str, pathogen: str, scenario: str, m: int) -> float:
        return min(1.0, WET[m - 1] * SCEN_RISK[scenario] * self._h(area_id) * PATH_MULT[pathogen])

    def risk_scenario(self, area_id, scenario):
        if area_id not in self._by_id or scenario not in SCEN_RISK:
            return []
        rows = []
        for p in PATH_MULT:
            for m in range(1, 13):
                r = self._risk(area_id, p, scenario, m)
                rows.append({"area_id": area_id, "pathogen_id": p, "scenario_id": scenario, "month": m,
                             "risk_mean": round(r, 3), "risk_min": round(r * 0.7, 3), "risk_max": round(min(1, r * 1.25), 3),
                             "favorable_days": round(r * calendar.monthrange(2025, m)[1], 1)})
        return rows

    def risk_monthly(self, area_id, pathogen, date_from, date_to):
        if area_id not in self._by_id:
            return []
        rows = []
        for y, m in _months_between(date_from, date_to):
            boost = NINO_YEARS.get(y, NINA_YEARS.get(y, 1.0))
            for p in ([pathogen] if pathogen else list(PATH_MULT)):
                r = min(1.0, WET[m - 1] * 0.72 * boost * self._h(area_id) * PATH_MULT[p])
                days = calendar.monthrange(y, m)[1]
                rows.append({"area_id": area_id, "pathogen_id": p, "month_date": f"{y}-{m:02d}-01",
                             "favorable_days": round(r * days), "risk_index": round(r, 3),
                             "max_consecutive_favorable_days": round(r * days * 0.6), "n_days_with_data": days})
        return rows

    def suitability(self, area_id, crop, scenarios=None):
        if area_id not in self._by_id:
            return []
        out = []
        for s in SCENARIOS:
            if scenarios and s["id"] not in scenarios:
                continue
            base = 0.72 + 0.2 * _rand("suit", area_id)
            score = round(base - (0.25 * _rand("suitf", area_id) + 0.05 if s["id"].startswith("ssp") else 0)
                          - (0.08 if s["id"] in ("nino", "actual") else 0), 2)
            cls = "optima" if score >= 0.85 else "apta" if score >= 0.6 else "marginal" if score >= 0.35 else "no_apta"
            limiting = ["rain_annual"] if s["id"] in ("nino", "actual") else ["temp_mean"] if s["id"].startswith("ssp") else []
            out.append({"area_id": area_id, "crop_id": crop, "scenario_id": s["id"], "score": score, "class": cls,
                        "limiting_factors": limiting, "details": {"temp_mean": 1.0 if not s["id"].startswith("ssp") else round(score + 0.05, 2),
                                                                  "rain_annual": round(score, 2)}})
        return out

    # ── pérdidas ──────────────────────────────────────
    def _loss_row(self, a: dict, crop: str, scenario: str) -> dict:
        lo, span = SCEN_LOSS[scenario]
        if a["kind"] == "canton":
            pct = round(lo + span * _rand("loss", a["id"]) * self._h(a["id"]) * 0.85, 1)
        else:
            kids = [c for c in self._areas if c["parent_id"] == a["id"]]
            w = [self._exposed(c["id"]) for c in kids]
            pct = round(sum(self._loss_row(c, crop, scenario)["loss_pct"] * wi for c, wi in zip(kids, w)) / sum(w), 1)
        ha = self._exposed(a["id"])
        loss_t = round(ha * YIELD_T_HA * pct / 100)
        rc = "bajo" if pct < 5 else "medio" if pct < 15 else "alto" if pct < 30 else "muy_alto"
        risk = {p: sum(self._risk(a["id"], p, scenario, m) for m in range(1, 7)) for p in PATH_MULT} if a["kind"] == "canton" else {}
        fav_m = round(sum(self._risk(a["id"], "monilia", scenario, m) * 30 for m in range(1, 7))) if a["kind"] == "canton" else None
        prov = self._by_id.get(a["parent_id"] or "", {}).get("name")
        return {"area_id": a["id"], "name": a["name"], "kind": a["kind"], "region": a["region"], "province": prov,
                "area_ha": a["area_ha"], "crop_id": crop, "scenario_id": scenario,
                "loss_pct": pct, "loss_pct_low": round(pct * 0.55, 1), "loss_pct_high": round(min(100, pct * 1.55), 1),
                "exposed_ha": ha, "expected_yield_t_ha": YIELD_T_HA, "price_usd_t": PRICE_USD_T,
                "loss_t": loss_t, "loss_usd": round(loss_t * PRICE_USD_T), "risk_class": rc,
                "top_factors": [
                    {"feature": "fav_days_monilia", "value": fav_m, "contribution_pct": round(pct * 0.45, 1)},
                    {"feature": "heavy_rain_days", "value": round(SCEN_RAIN[scenario] * 9), "contribution_pct": round(pct * 0.25, 1)},
                    {"feature": "nino12_anom_jan_jun", "value": {"nino": 1.8, "actual": 3.2}.get(scenario, 0.1), "contribution_pct": round(pct * 0.2, 1)},
                ] if a["kind"] == "canton" else [],
                "model_name": "mock_cacao_loss", "_risk": risk}

    def losses(self, crop, scenario=None, kind=None, province=None, area_id=None, with_geom=False):
        if crop != "cacao":
            return []
        out = []
        for a in self._areas:
            if kind and a["kind"] != kind:
                continue
            if area_id and a["id"] != area_id:
                continue
            prov = self._by_id.get(a["parent_id"] or "", {}).get("name")
            if province and prov != province:
                continue
            for s in ([scenario] if scenario else list(SCEN_LOSS)):
                row = self._loss_row(a, crop, s)
                row.pop("_risk")
                row.pop("expected_yield_t_ha")
                row.pop("price_usd_t")
                if with_geom:
                    row["geom"] = a["geom"]
                out.append(row)
        return out

    def loss_full(self, model_version_id, area_id, crop, scenario):
        a = self._by_id.get(area_id)
        if not a or crop != "cacao" or scenario not in SCEN_LOSS:
            return None
        row = self._loss_row(a, crop, scenario)
        row.pop("_risk")
        return {**row, "id": _id("pred", area_id, scenario), "model_version_id": model_version_id}

    def available_scenarios(self, crop):
        return set(SCEN_LOSS) if crop == "cacao" else set()

    def zones(self, crop, future):
        out = []
        for a in self._areas:
            if a["kind"] != "canton":
                continue
            now = next(s["score"] for s in self.suitability(a["id"], crop, ["normal"]))
            fut = next(s["score"] for s in self.suitability(a["id"], crop, [future]))
            risk = round(sum(self._risk(a["id"], "monilia", "nino", m) for m in range(1, 7)) / 6, 2)
            apt = fut >= 0.6
            cls = ("segura" if risk < 0.6 else "manejo") if apt else ("transicion" if risk < 0.6 else "critica")
            out.append({"area_id": a["id"], "crop_id": crop, "future_scenario_id": future, "zone_class": cls,
                        "suitability_now": now, "suitability_future": fut, "nino_risk": risk,
                        "areas": {"name": a["name"], "parent_id": a["parent_id"]}})
        return out

    # ── validación en campo ───────────────────────────
    def observations(self, area_id, pathogen, source, limit):
        obs = []
        for i, (prov, name, lat, lon) in enumerate(CANTONS[:6]):
            aid = _id("canton", prov, name)
            obs.append({"id": i + 1, "area_id": aid, "pathogen_id": "monilia", "observed_on": f"2024-0{(i % 6) + 1}-15",
                        "lat": lat + 0.01, "lon": lon - 0.01, "pods_total": None, "pods_diseased": None, "incidence_pct": None,
                        "severity": None, "source": "gbif", "external_id": f"mock-{i}", "notes": "Ocurrencia sintética"})
        return [o for o in obs if (not area_id or o["area_id"] == area_id)
                and (not pathogen or o["pathogen_id"] == pathogen) and (not source or o["source"] == source)][:limit]

    def insert_observation(self, token, row):
        return {"id": 999, **row, "created_at": date.today().isoformat(), "mock": True}
