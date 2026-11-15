"""Clima por escenario, riesgo mensual por patógeno y chequeo contra los requerimientos del cultivo."""
from collections import defaultdict

from ..core.errors import bad_request
from ..data import get_source
from . import labels

SCENARIOS = {"normal", "nino", "nino_extremo", "nina", "actual", "ssp245_2050", "ssp585_2050"}


def check_scenario(s: str) -> str:
    if s not in SCENARIOS:
        raise bad_request("invalid_scenario", f"Escenario inválido: {s}. Opciones: {sorted(SCENARIOS)}")
    return s


def climate_summary(area_id: str, scenario: str, variables: list[str] | None = None) -> dict:
    rows = get_source().scenario_climate(area_id, scenario, variables)
    by_var: dict[str, list[dict]] = defaultdict(list)
    meta: dict[str, dict] = {}
    for r in rows:
        by_var[r["variable_id"]].append({"month": r["month"], "mean": _f(r["value_mean"]),
                                         "min": _f(r.get("value_min")), "max": _f(r.get("value_max"))})
        meta[r["variable_id"]] = {"method": r.get("method"), "n_members": r.get("n_members")}
    units = {v["id"]: v["unit"] for v in get_source().variables()}
    out = {}
    for v, months in by_var.items():
        months.sort(key=lambda m: m["month"])
        vals = [m["mean"] for m in months if m["mean"] is not None]
        op = labels.VARIABLE_OPS.get(v, "mean")
        annual = (sum(vals) if op == "sum" else sum(vals) / len(vals)) if vals else None
        out[v] = {"unit": units.get(v), **meta[v], "months": months,
                  "annual": round(annual, 2) if annual is not None else None, "annual_op": op}
    return out


def risk_window(crop: str, region: str | None) -> list[int]:
    rows = [p for p in get_source().phenology(crop) if p.get("is_risk_window")]
    reg = region or "costa"
    for p in rows:
        if p["region"] == reg:
            return sorted(p["months"])
    return [1, 2, 3, 4, 5, 6]


def risk_table(area_id: str, scenario: str, window: list[int]) -> dict:
    rows = get_source().risk_scenario(area_id, scenario)
    pathogens = sorted({r["pathogen_id"] for r in rows})
    months = {m: {"month": m} for m in range(1, 13)}
    fav: dict[str, float] = defaultdict(float)
    totals: dict[str, float] = defaultdict(float)
    for r in rows:
        months[r["month"]][r["pathogen_id"]] = _f(r["risk_mean"])
        if r["month"] in window:
            totals[r["pathogen_id"]] += _f(r["risk_mean"]) or 0
            fav[r["pathogen_id"]] += _f(r.get("favorable_days")) or 0
    peak = None
    for r in rows:
        if peak is None or (_f(r["risk_mean"]) or 0) > peak["risk"]:
            peak = {"pathogen": r["pathogen_id"], "month": r["month"], "risk": _f(r["risk_mean"])}
    dominant = max(totals, key=totals.get) if totals else None
    s = sum(totals.values())
    shares = {p: round(v / s, 3) for p, v in totals.items()} if s else {}
    return {"pathogens": pathogens, "months": list(months.values()) if rows else [], "peak": peak,
            "dominant_pathogen": dominant, "risk_window_months": window, "shares": shares,
            "favorable_days_window": {p: round(v) for p, v in fav.items()},
            "risk_window_mean": {p: round(v / len(window), 3) for p, v in totals.items()} if window else {}}


def requirement_check(crop: str, climate: dict, static: dict | None) -> list[dict]:
    reqs = {r["parameter"]: r for r in get_source().crop_requirements(crop)}
    values = {
        "temp_mean": (climate.get("t2m") or {}).get("annual"),
        "rain_annual": (climate.get("precip") or {}).get("annual"),
        "altitude": (static or {}).get("elevation_mean_m"),
        "ph": (static or {}).get("soil_ph"),
    }
    out = []
    for p, v in values.items():
        r = reqs.get(p)
        if r is None:
            continue
        opt = [_f(r.get("opt_min")), _f(r.get("opt_max"))]
        ab = [_f(r.get("abs_min")), _f(r.get("abs_max"))]
        out.append({"parameter": p, "label": labels.PARAMETERS.get(p, p), "value": _f(v), "unit": r.get("unit"),
                    "opt": opt, "abs": ab, "status": _status(_f(v), opt, ab)})
    return out


def _status(v: float | None, opt: list, ab: list) -> str:
    if v is None:
        return "sin_dato"
    lo, hi = opt
    if (lo is None or v >= lo) and (hi is None or v <= hi):
        return "ok"
    alo, ahi = ab
    if alo is None and ahi is None:
        return "warn"
    if (alo is None or v >= alo) and (ahi is None or v <= ahi):
        return "warn"
    return "bad"


def _f(v) -> float | None:
    return None if v is None else float(v)
