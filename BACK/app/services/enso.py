"""Estado de El Niño. Lee enso_index; si la tabla está vacía, consulta NOAA CPC en vivo (sin escribir)."""
import logging

import httpx

from ..core.cache import cached
from ..core.config import get_settings
from ..data import get_source

log = logging.getLogger(__name__)

SEAS_MID = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7,
            "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
MID_SEAS = {v: k for k, v in SEAS_MID.items()}


def phase_of(index_id: str, value: float) -> str:
    t = 0.5 if index_id == "oni" else 0.4
    return "nino" if value >= t else "nina" if value <= -t else "neutral"


def intensity_of(oni: float | None) -> str | None:
    if oni is None:
        return None
    a = abs(oni)
    if a < 0.5:
        return None
    return "debil" if a < 1.0 else "moderado" if a < 1.5 else "fuerte" if a < 2.0 else "muy_fuerte"


@cached(ttl=6 * 3600, maxsize=4)
def noaa_live() -> dict[str, list[dict]]:
    """ONI y Niño 1+2 desde NOAA CPC (texto plano). Vacío si NOAA no responde."""
    s = get_settings()
    out: dict[str, list[dict]] = {"oni": [], "nino12_anom": []}
    try:
        with httpx.Client(timeout=20) as c:
            for line in c.get(s.noaa_oni_url).text.splitlines()[1:]:
                p = line.split()
                if len(p) == 4 and p[0] in SEAS_MID:
                    v = float(p[3])
                    out["oni"].append({"index_id": "oni", "month_date": f"{p[1]}-{SEAS_MID[p[0]]:02d}-01",
                                       "value": v, "phase": phase_of("oni", v)})
            for line in c.get(s.noaa_sst_url).text.splitlines()[1:]:
                p = line.split()
                if len(p) >= 10:
                    v = float(p[3])
                    out["nino12_anom"].append({"index_id": "nino12_anom", "month_date": f"{int(p[0])}-{int(p[1]):02d}-01",
                                               "value": v, "phase": phase_of("nino12_anom", v)})
    except (httpx.HTTPError, ValueError) as e:
        log.warning("NOAA CPC no disponible: %s", e)
    return out


def _latest(index_id: str) -> tuple[dict | None, str]:
    row = get_source().enso_latest(index_id)
    if row:
        return row, "db"
    live = noaa_live().get(index_id) or []
    return (live[-1], "noaa_live") if live else (None, "none")


def history(index_ids: list[str], date_from: str | None, date_to: str | None) -> dict[str, list[dict]]:
    rows = get_source().enso_index(index_ids, date_from, date_to)
    if not rows:
        live = noaa_live()
        rows = [r for i in index_ids for r in live.get(i, [])
                if (not date_from or r["month_date"] >= date_from) and (not date_to or r["month_date"] <= date_to)]
    out: dict[str, list[dict]] = {i: [] for i in index_ids}
    for r in rows:
        out.setdefault(r["index_id"], []).append(
            {"month": r["month_date"][:7], "value": float(r["value"]), "phase": r.get("phase")})
    return out


@cached(ttl=3600, maxsize=4)
def current() -> dict:
    oni, src1 = _latest("oni")
    n12, src2 = _latest("nino12_anom")
    oni_v = float(oni["value"]) if oni else None
    n12_v = float(n12["value"]) if n12 else None

    phase = "neutral"
    if oni_v is not None and phase_of("oni", oni_v) != "neutral":
        phase = phase_of("oni", oni_v)
    elif n12_v is not None and phase_of("nino12_anom", n12_v) == "nino":
        phase = "nino"   # Niño costero

    event = next((e for e in get_source().enso_events() if e.get("end_month") is None), None)
    intensity = (event or {}).get("intensity") or intensity_of(oni_v)

    if phase == "nino":
        msg = "El Niño en curso"
        if intensity:
            msg = f"El Niño {intensity.replace('_', ' ')} en curso"
        if n12_v is not None:
            msg += f": el mar frente a Ecuador está {n12_v:.1f} °C más caliente de lo normal."
    elif phase == "nina":
        msg = "La Niña en curso: lluvias por debajo de lo normal en la Costa."
    else:
        msg = "Condiciones neutrales: sin El Niño ni La Niña."

    oni_month = int(oni["month_date"][5:7]) if oni else None
    return {
        "phase": phase, "intensity": intensity,
        "oni": {"value": oni_v, "month": oni["month_date"][:7], "season": MID_SEAS.get(oni_month)} if oni else None,
        "nino12_anom": {"value": n12_v, "month": n12["month_date"][:7]} if n12 else None,
        "event": event,
        "active_scenario": {"nino": "nino", "nina": "nina"}.get(phase, "normal"),
        "message_es": msg,
        "source": "NOAA CPC", "origin": src1 if src1 == src2 else f"{src1}/{src2}",
    }


def years() -> list[dict]:
    """v_enso_year_class; si está vacía, la misma regla sobre NOAA en vivo (promedio ene–jun):
    Niño si ONI ≥ 0.5 o Niño 1+2 ≥ 0.4; Niña si ONI ≤ −0.5; Niño costero si Niño 1+2 ≥ 0.4 y ONI < 0.5."""
    rows = get_source().enso_years()
    if rows:
        return rows
    live = noaa_live()
    acc: dict[int, dict[str, list[float]]] = {}
    for idx in ("oni", "nino12_anom"):
        for r in live.get(idx, []):
            y, m = int(r["month_date"][:4]), int(r["month_date"][5:7])
            if m <= 6:
                acc.setdefault(y, {"oni": [], "nino12_anom": []})[idx].append(float(r["value"]))
    out = []
    for y in sorted(acc):
        oni = sum(acc[y]["oni"]) / len(acc[y]["oni"]) if acc[y]["oni"] else None
        n12 = sum(acc[y]["nino12_anom"]) / len(acc[y]["nino12_anom"]) if acc[y]["nino12_anom"] else None
        cls = ("nino" if (oni is not None and oni >= 0.5) or (n12 is not None and n12 >= 0.4)
               else "nina" if oni is not None and oni <= -0.5 else "neutral")
        out.append({"year": y, "oni_jan_jun": round(oni, 3) if oni is not None else None,
                    "nino12_anom_jan_jun": round(n12, 3) if n12 is not None else None, "enso_class": cls,
                    "is_coastal_nino": n12 is not None and n12 >= 0.4 and (oni or 0) < 0.5, "origin": "noaa_live"})
    return out
