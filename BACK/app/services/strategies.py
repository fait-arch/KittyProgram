"""Evaluación de estrategias de adaptación, al vuelo (no escribe strategy_evaluations).

pérdida_con_estrategia = loss_pct × (1 − Σ peso_objetivo × reducción_objetivo)
peso de cada patógeno  = participación del patógeno en el riesgo de la ventana de cultivo
beneficio_neto         = pérdida_evitada_usd + ingreso_protegido_usd − costo_usd_ha × ha

Los valores de reducción y costo salen de strategy_effects / adaptation_strategies. Mientras
Datos no los llene, se usan los DEFAULT_* de abajo, marcados como supuestos por validar.
"""
from ..core.errors import bad_request
from ..data import get_source
from . import climate, labels, losses
from .territory import get_area

# ── Supuestos REFERENCIALES (reemplazar con literatura / INIAP en strategy_effects) ──
DEFAULT_EFFECTS: dict[tuple[str, str], tuple[float, float]] = {
    ("sanitario", "monilia"): (25, 50), ("sanitario", "phytophthora"): (20, 40), ("sanitario", "escoba_bruja"): (20, 40),
    ("drenaje_sombra", "phytophthora"): (15, 35), ("drenaje_sombra", "encharcamiento"): (30, 60),
    ("drenaje_sombra", "calor"): (20, 40), ("diversificacion", "ingreso"): (15, 30),
}
DEFAULT_COST_USD_HA = {"actual": 0, "sanitario": 120, "drenaje_sombra": 180, "diversificacion": 90}
# Parte de la pérdida atribuida a problemas no fúngicos (supuesto): el resto se reparte entre patógenos.
NON_DISEASE_WEIGHT = {"encharcamiento": 0.15, "calor": 0.05}
ATTRIBUTES = {  # 0–1: mejora del suelo, manejo del agua, mano de obra que exige
    "actual": {"soil": 0.0, "water": 0.0, "labor": 0.0},
    "sanitario": {"soil": 0.2, "water": 0.0, "labor": 0.8},
    "drenaje_sombra": {"soil": 0.6, "water": 0.9, "labor": 0.5},
    "diversificacion": {"soil": 0.7, "water": 0.4, "labor": 0.6},
}
RISKS = {
    "actual": ["Sin cambios, la pérdida esperada se mantiene en años Niño."],
    "sanitario": ["Requiere mano de obra semanal en la época lluviosa.",
                  "Las mazorcas retiradas deben enterrarse o cubrirse; si se dejan en el suelo siguen esparciendo esporas."],
    "drenaje_sombra": ["Inversión inicial en canales; revisar pendiente y salida del agua con un técnico.",
                       "Demasiada sombra aumenta la humedad y puede favorecer la moniliasis: regular, no cerrar."],
    "diversificacion": ["Plátano y maderables compiten por luz y agua si se siembran muy cerca.",
                        "Revisar mercado local para los cultivos nuevos antes de sembrar."],
}
BENEFITS = {
    "actual": [],
    "sanitario": ["Baja la cantidad de esporas en la finca", "Actúa sobre moniliasis, mazorca negra y escoba de bruja"],
    "drenaje_sombra": ["Menos encharcamiento y menos mazorca negra", "Sombra regulada protege del calor", "Mejora la estructura del suelo"],
    "diversificacion": ["Protege el ingreso si el cacao cae", "Rotación de intercalados (maíz, leguminosas) en cacao joven mejora el suelo",
                        "Plátano y maderables dan ingreso adicional"],
}
PRIORITY_KEYS = ("ingreso", "costo", "suelo", "agua", "mano_obra")


def parse_priorities(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    out = {}
    for part in raw.split(","):
        if not part.strip():
            continue
        k, _, v = part.partition(":")
        k = k.strip()
        if k not in PRIORITY_KEYS or not v.strip().isdigit() or not 0 <= int(v) <= 5:
            raise bad_request("invalid_priorities", f"Prioridad inválida '{part}'. Formato: ingreso:5,costo:3 (claves {PRIORITY_KEYS}, 0–5)")
        out[k] = int(v)
    return out


def _effects() -> dict[tuple[str, str], dict]:
    out = {}
    for e in get_source().strategy_effects():
        key = (e["strategy_id"], e["target"])
        lo, hi = e.get("reduction_pct_low"), e.get("reduction_pct_high")
        if lo is not None and hi is not None:
            out[key] = {"low": float(lo), "high": float(hi), "validated": bool(e.get("validated")), "source": e.get("source_ref") or "strategy_effects"}
        elif key in DEFAULT_EFFECTS:
            dl, dh = DEFAULT_EFFECTS[key]
            out[key] = {"low": dl, "high": dh, "validated": False, "source": "supuesto del backend (por validar)"}
    for key, (dl, dh) in DEFAULT_EFFECTS.items():
        out.setdefault(key, {"low": dl, "high": dh, "validated": False, "source": "supuesto del backend (por validar)"})
    return out


def evaluate(area_id: str, crop: str, scenario: str, priorities: dict[str, int] | None = None) -> dict:
    area = get_area(area_id)
    loss = losses.loss_for(area_id, crop, scenario)
    window = climate.risk_window(crop, area.get("region"))
    risk = climate.risk_table(area_id, scenario, window)
    clim = climate.climate_summary(area_id, scenario, ["heavy_rain_days", "saturated_days", "rh_mean", "precip"])
    effects = _effects()
    catalog = {s["id"]: s for s in get_source().strategies()}

    disease_weight = 1 - sum(NON_DISEASE_WEIGHT.values())
    shares = risk["shares"] or {"monilia": 0.5, "phytophthora": 0.35, "escoba_bruja": 0.15}
    weights = {p: disease_weight * s for p, s in shares.items()} | NON_DISEASE_WEIGHT

    ha = loss["exposed_ha"] or 0
    loss_usd = loss["loss_usd"] or 0
    pct = loss["loss_pct"] or 0
    items = []
    for sid, s in catalog.items():
        targets = {t: e for (st, t), e in effects.items() if st == sid}
        red_lo = sum(weights.get(t, 0) * e["low"] / 100 for t, e in targets.items() if t != "ingreso")
        red_hi = sum(weights.get(t, 0) * e["high"] / 100 for t, e in targets.items() if t != "ingreso")
        red_mid = (red_lo + red_hi) / 2
        inc = targets.get("ingreso")
        inc_mid = ((inc["low"] + inc["high"]) / 200) if inc else 0.0
        avoided = loss_usd * red_mid
        income_protected = (loss_usd - avoided) * inc_mid
        cost_ha = s.get("cost_usd_ha_year")
        cost_src = "adaptation_strategies"
        if cost_ha is None:
            cost_ha, cost_src = DEFAULT_COST_USD_HA.get(sid, 0), "supuesto del backend (por validar)"
        cost_total = float(cost_ha) * ha
        validated = bool(s.get("validated")) and all(e["validated"] for e in targets.values())

        gaps = []
        if any(not e["validated"] for e in targets.values()):
            gaps.append("La reducción de pérdida viene de valores referenciales, no medidos en este cantón.")
        if cost_src != "adaptation_strategies":
            gaps.append("El costo por hectárea es un supuesto; ajustarlo con precios locales de mano de obra e insumos.")
        if not risk["shares"]:
            gaps.append("No hay riesgo por patógeno calculado para este escenario: se usó un reparto típico.")

        items.append({
            "strategy_id": sid, "name_es": s["name_es"], "description": s.get("description"),
            "is_current": sid == "actual",
            "expected_loss_pct": round(pct * (1 - red_mid), 1),
            "expected_loss_pct_range": [round(pct * (1 - red_hi), 1), round(pct * (1 - red_lo), 1)],
            "loss_reduction_pct": round(red_mid * 100, 1),
            "avoided_loss_usd": round(avoided), "income_protected_usd": round(income_protected),
            "cost_usd_ha_year": float(cost_ha), "cost_total_usd": round(cost_total),
            "net_benefit_usd": round(avoided + income_protected - cost_total),
            "targets": [{"target": t, "label": labels.STRATEGY_TARGET_LABELS.get(t, t), "reduction_pct": [e["low"], e["high"]],
                         "weight": round(weights.get(t, 0), 3) if t != "ingreso" else None, "source": e["source"],
                         "validated": e["validated"]} for t, e in targets.items()],
            "why": _why(sid, risk, clim, area["name"]),
            "evidence": _evidence(sid, risk, clim, scenario, window),
            "benefits": BENEFITS.get(sid, []), "data_gaps": gaps, "risks": RISKS.get(sid, []),
            "attributes": ATTRIBUTES.get(sid, {"soil": 0, "water": 0, "labor": 0}),
            "validated": validated,
        })

    _rank(items, priorities or {})
    return {"area_id": area_id, "area_name": area["name"], "crop": crop, "scenario": scenario,
            "baseline_loss_pct": pct, "baseline_loss_usd": loss_usd, "exposed_ha": ha,
            "dominant_pathogen": risk["dominant_pathogen"], "priorities_applied": priorities or {},
            "items": items, "method": "Cálculo al vuelo: pérdida del modelo × reducción por objetivo ponderada por el riesgo del cantón.",
            "disclaimer": labels.DISCLAIMER}


def _rank(items: list[dict], pri: dict[str, int]) -> None:
    def norm(vals):
        lo, hi = min(vals), max(vals)
        return [0.5 if hi == lo else (v - lo) / (hi - lo) for v in vals]

    if pri:
        benefit = norm([i["avoided_loss_usd"] + i["income_protected_usd"] for i in items])
        cost = norm([i["cost_total_usd"] for i in items])
        for i, b, c in zip(items, benefit, cost):
            a = i["attributes"]
            i["priority_score"] = round(pri.get("ingreso", 0) * b + pri.get("costo", 0) * (1 - c)
                                        + pri.get("suelo", 0) * a["soil"] + pri.get("agua", 0) * a["water"]
                                        + pri.get("mano_obra", 0) * (1 - a["labor"]), 3)
        items.sort(key=lambda i: (-i["priority_score"], -i["net_benefit_usd"]))
    else:
        items.sort(key=lambda i: -i["net_benefit_usd"])
    items.sort(key=lambda i: i["is_current"])   # la actual siempre al final: es la referencia
    for n, i in enumerate(items, 1):
        i["rank"] = n


def _month_names(ms: list[int]) -> str:
    names = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{names[ms[0] - 1]}–{names[ms[-1] - 1]}" if ms else ""


def _why(sid: str, risk: dict, clim: dict, area: str) -> str:
    dom = labels.STRATEGY_TARGET_LABELS.get(risk["dominant_pathogen"] or "", "las enfermedades")
    heavy = (clim.get("heavy_rain_days") or {}).get("annual")
    if sid == "sanitario":
        return f"En {area} la {dom} es el problema que más pesa en la época de riesgo; retirar mazorcas enfermas corta su ciclo."
    if sid == "drenaje_sombra":
        extra = f" (~{heavy:.0f} días de aguacero al año en este escenario)" if heavy else ""
        return f"El exceso de lluvia{extra} encharca el suelo y favorece la mazorca negra; drenar y regular la sombra lo reduce."
    if sid == "diversificacion":
        return "No reduce la enfermedad, pero reparte el riesgo: si el cacao cae en un año Niño, otros cultivos sostienen el ingreso."
    return "Es la referencia: lo que pasaría sin cambiar el manejo."


def _evidence(sid: str, risk: dict, clim: dict, scenario: str, window: list[int]) -> list[dict]:
    ev = []
    per = _month_names(window)
    fav = risk["favorable_days_window"]
    if sid in ("sanitario", "actual") and fav:
        for p, d in sorted(fav.items(), key=lambda x: -x[1])[:2]:
            ev.append({"variable_id": "rh_mean", "source_id": "era5_land",
                       "statement": f"{d} días favorables a {labels.STRATEGY_TARGET_LABELS.get(p, p)} en {per} (escenario {scenario})"})
    if sid == "drenaje_sombra":
        for v, src, txt in (("heavy_rain_days", "gpm_imerg", "días de aguacero (> 50 mm) al año"),
                            ("saturated_days", "smap_l4", "días con suelo saturado al año")):
            a = (clim.get(v) or {}).get("annual")
            if a is not None:
                ev.append({"variable_id": v, "source_id": src, "statement": f"{a:.0f} {txt} (escenario {scenario})"})
    if sid == "diversificacion":
        p = (clim.get("precip") or {}).get("annual")
        if p is not None:
            ev.append({"variable_id": "precip", "source_id": "gpm_imerg",
                       "statement": f"{p:.0f} mm de lluvia al año (óptimo del cacao: 1 200–3 000 mm)"})
    return ev
