"""Pérdidas estimadas (v_loss_map / loss_predictions del modelo activo)."""
from collections import Counter

from ..core.cache import cached
from ..core.config import get_settings
from ..core.errors import not_found
from ..data import get_source
from . import labels

LOSS_FIELDS = ("loss_pct", "loss_pct_low", "loss_pct_high", "exposed_ha", "loss_t", "loss_usd", "risk_class")


def _num(v):
    return None if v is None else float(v)


def _item(r: dict) -> dict:
    item = {"area_id": r["area_id"], "name": r["name"], "kind": r.get("kind"), "province": r.get("province")}
    for k in LOSS_FIELDS:
        item[k] = r.get(k) if k == "risk_class" else _num(r.get(k))
    if not item["risk_class"]:
        item["risk_class"] = labels.risk_class(item["loss_pct"])
    return item


@cached(ttl=get_settings().cache_ttl_seconds)
def active_model(crop: str) -> dict | None:
    return get_source().active_model(crop)


def model_info(crop: str) -> dict | None:
    m = active_model(crop)
    if not m:
        return None
    metrics = m.get("metrics") or {}
    return {"id": m["id"], "name": m["name"], "algorithm": m.get("algorithm"), "mae": metrics.get("mae"),
            "trained_years": [m.get("train_start_year"), m.get("train_end_year")], "n_samples": m.get("n_samples")}


@cached(ttl=get_settings().cache_ttl_seconds)
def list_losses(crop: str, scenario: str, kind: str | None, province: str | None) -> dict:
    rows = get_source().losses(crop, scenario=scenario, kind=kind, province=province)
    items = sorted((_item(r) for r in rows), key=lambda i: -(i["loss_pct"] or 0))
    return {"scenario": scenario, "crop": crop, "model": model_info(crop),
            "classes": labels.RISK_CLASSES, "count": len(items), "items": items}


def summary(crop: str, scenario: str, province: str | None, vs: str | None) -> dict:
    kind = "canton"
    items = list_losses(crop, scenario, kind, province)["items"]
    if not items:   # quizá solo hay predicciones por provincia
        kind = "province"
        items = list_losses(crop, scenario, kind, province)["items"]

    def tot(rows, k):
        return round(sum(r[k] or 0 for r in rows), 1)

    def low_high(rows):
        # loss_t es proporcional a loss_pct → escalar por el cociente del intervalo
        def scaled(key):
            return sum((r["loss_t"] or 0) * (r[key] if r[key] is not None else r["loss_pct"]) / r["loss_pct"]
                       for r in rows if r["loss_pct"])
        return round(scaled("loss_pct_low")), round(scaled("loss_pct_high"))

    low, high = low_high(items)
    out = {
        "scenario": scenario, "crop": crop, "level": kind,
        "scope": {"kind": "province", "name": province} if province else {"kind": "country", "name": "Ecuador"},
        "totals": {"exposed_ha": tot(items, "exposed_ha"), "loss_t": tot(items, "loss_t"),
                   "loss_t_low": low, "loss_t_high": high, "loss_usd": tot(items, "loss_usd")},
        "by_class": dict(Counter(i["risk_class"] for i in items)),
        "top_areas": [{"area_id": i["area_id"], "name": i["name"], "loss_usd": i["loss_usd"], "loss_pct": i["loss_pct"]}
                      for i in sorted(items, key=lambda i: -(i["loss_usd"] or 0))[:5]],
        "note": "Los intervalos se suman (cota conservadora).",
    }
    if vs:
        other = list_losses(crop, vs, kind, province)["items"]
        o_t, o_usd = tot(other, "loss_t"), tot(other, "loss_usd")
        out["vs"] = {"scenario": vs, "loss_t": o_t, "loss_usd": o_usd,
                     "delta_t": round(out["totals"]["loss_t"] - o_t, 1),
                     "delta_usd": round(out["totals"]["loss_usd"] - o_usd, 1)}
    return out


def loss_for(area_id: str, crop: str, scenario: str, required: bool = True) -> dict | None:
    """Fila completa (incluye rendimiento y precio) del modelo activo para un área."""
    m = active_model(crop)
    row = get_source().loss_full(m["id"], area_id, crop, scenario) if m else None
    if row is None and required:
        raise not_found("loss_not_found", f"No hay predicción de pérdida para este área en el escenario '{scenario}'")
    if row:
        for k in ("loss_pct", "loss_pct_low", "loss_pct_high", "exposed_ha", "expected_yield_t_ha",
                  "loss_t", "price_usd_t", "loss_usd"):
            row[k] = _num(row.get(k))
        row["risk_class"] = row.get("risk_class") or labels.risk_class(row["loss_pct"])
    return row


def factors(row: dict) -> list[dict]:
    out = []
    for f in (row.get("top_factors") or [])[:5]:
        contrib = f.get("contribution_pct", f.get("contribution"))
        out.append({"feature": f.get("feature"), "label": labels.feature_label(f.get("feature", "")),
                    "value": f.get("value"), "contribution_pct": _num(contrib)})
    return out
