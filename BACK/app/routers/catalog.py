"""Sistema y catálogos: /meta, /crops, /scenarios, /strategies."""
from fastapi import APIRouter, Query

from ..core.cache import cached
from ..core.errors import not_found
from ..data import get_source
from ..services import labels, losses, strategies

router = APIRouter(tags=["catálogos"])


@cached(ttl=24 * 3600)
def _meta(crop: str) -> dict:
    src = get_source()
    m = losses.active_model(crop)
    return {
        "sources": src.sources(), "variables": src.variables(),
        "model": ({k: m.get(k) for k in ("id", "name", "algorithm", "features", "metrics", "train_start_year",
                                         "train_end_year", "n_samples", "created_at")} if m else None),
        "limitations": labels.LIMITATIONS, "attribution": labels.ATTRIBUTION, "disclaimer": labels.DISCLAIMER,
        "data_source": src.name,
    }


@router.get("/meta", summary="Fuentes, variables, modelo activo y limitaciones")
def meta(crop: str = "cacao"):
    return _meta(crop)


@router.get("/crops")
def crops(region: str | None = None):
    rows = get_source().crops()
    return [c for c in rows if not region or region in (c.get("region") or [])]


@router.get("/crops/{crop}/requirements", summary="Requerimientos ECOCROP del cultivo")
def requirements(crop: str):
    rows = get_source().crop_requirements(crop)
    if not rows:
        raise not_found("crop_not_found", f"Sin requerimientos para '{crop}'")
    num, cat = [], []
    for r in rows:
        label = labels.PARAMETERS.get(r["parameter"], r["parameter"])
        if r.get("value_text"):
            cat.append({"parameter": r["parameter"], "label": label, "value": r["value_text"]})
        else:
            num.append({"parameter": r["parameter"], "label": label, "unit": r.get("unit"),
                        **{k: (float(r[k]) if r.get(k) is not None else None) for k in ("opt_min", "opt_max", "abs_min", "abs_max")}})
    return {"crop_id": crop, "source": rows[0].get("source_ref") or "ECOCROP (OpenCLIM/ecocrop)", "numeric": num, "categorical": cat}


@router.get("/crops/{crop}/pathogens", summary="Enfermedades y la regla de 'día favorable'")
def pathogens(crop: str):
    out = []
    for p in get_source().pathogens(crop):
        th = p.get("disease_thresholds") or []
        out.append({k: p.get(k) for k in ("id", "name_es", "scientific_name", "organ_affected", "spread_by", "description")}
                   | {"rule_text": labels.rule_text(th), "validated": bool(th) and all(t.get("validated") for t in th),
                      "thresholds": [{"variable_id": t["variable_id"], "min": t.get("min_value"), "max": t.get("max_value"),
                                      "unit": t.get("unit"), "resolution": t.get("resolution", "daily")} for t in th]})
    return out


@router.get("/crops/{crop}/phenology", summary="Calendario del cultivo y ventana de riesgo")
def phenology(crop: str, region: str | None = None):
    return [p for p in get_source().phenology(crop) if not region or p["region"] == region]


@router.get("/scenarios")
def scenarios(phase: int | None = Query(None, ge=1, le=3), crop: str = "cacao"):
    src = get_source()
    avail = src.available_scenarios(crop)
    return [{"id": s["id"], "name_es": s["name_es"], "kind": s["kind"], "phase": s["phase"],
             "period": [s.get("period_start"), s.get("period_end")], "ssp": s.get("ssp"),
             "description": s.get("description"), "available": s["id"] in avail}
            for s in sorted(src.scenarios(), key=lambda s: ORDER.index(s["id"]) if s["id"] in ORDER else 99)
            if phase is None or s["phase"] == phase]


ORDER = ["normal", "nino", "nina", "actual", "ssp245_2050", "ssp585_2050"]


@router.get("/strategies", summary="Catálogo de estrategias con sus efectos y supuestos")
def strategy_catalog():
    effects = strategies._effects()
    out = []
    for s in get_source().strategies():
        out.append({**s, "cost_usd_ha_year": s.get("cost_usd_ha_year") if s.get("cost_usd_ha_year") is not None
                    else strategies.DEFAULT_COST_USD_HA.get(s["id"]),
                    "effects": [{"target": t, "label": labels.STRATEGY_TARGET_LABELS.get(t, t),
                                 "reduction_pct": [e["low"], e["high"]], "source": e["source"], "validated": e["validated"]}
                                for (sid, t), e in effects.items() if sid == s["id"]],
                    "attributes": strategies.ATTRIBUTES.get(s["id"])})
    return out
