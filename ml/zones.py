"""Matriz de decisión por área: aptitud a largo plazo (FAO GAEZ v4, 2050) × riesgo por El Niño (modelo).

    ml/.venv/bin/python -m ml.etl.gaez     # aptitud GAEZ por área (una vez)
    ml/.venv/bin/python -m ml.zones        # → artifacts/zones_v1.csv

Las dos preguntas son distintas y se complementan:
  · ¿Seguirá siendo buena la zona para el cacao?  → índice de aptitud GAEZ v4 en 2050 (RCP8.5,
    manejo alto; 0–10 000). Apta si ≥ 4 000 (clase "media" o mejor).
  · ¿Cuánto se pierde cuando llega un Niño costero extremo?  → pérdida del modelo en el escenario
    `nino_extremo`. Riesgo alto si ≥ 30 %.

Zonas (mismos nombres que la tabla `zone_classification` de Supabase y el ZoneMatrix del front):
    segura      apta y riesgo bajo   → seguir con cacao; buenas prácticas
    manejo      apta y riesgo alto   → invertir en adaptación: drenaje, cosecha sanitaria, poda, seguro
    transicion  poco apta, riesgo bajo → diversificar de a poco (cacao asociado con otros cultivos)
    critica     poco apta, riesgo alto → evaluar otro cultivo o sistema agroforestal mixto
Los cortes (4 000 y 30 %) son decisiones del equipo, documentadas aquí: cambiarlos cambia las zonas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ARTIFACTS, DATA_PROCESSED
from .predict import VERSION

SUIT_MIN = 4000.0
RISK_MAX = 30.0
OUT = ARTIFACTS / f"zones_{VERSION}"
ACTION = {
    "segura": "Seguir con cacao y buenas prácticas; el riesgo por El Niño es bajo.",
    "manejo": "Apta para cacao pero muy expuesta a El Niño: invertir en drenaje, cosecha sanitaria semanal, "
              "poda y seguro agrícola antes de la temporada de lluvias.",
    "transicion": "Aptitud baja a largo plazo: diversificar de a poco (cacao asociado con otros cultivos).",
    "critica": "Aptitud baja y alta pérdida en un Niño extremo: evaluar otro cultivo o un sistema "
               "agroforestal mixto; si se mantiene cacao, adaptación intensiva.",
}


def zone(suit: float, risk: float) -> str | None:
    if pd.isna(suit) or pd.isna(risk):
        return None
    apta, alto = suit >= SUIT_MIN, risk >= RISK_MAX
    return {(True, False): "segura", (True, True): "manejo", (False, False): "transicion",
            (False, True): "critica"}[(apta, alto)]


def run(verbose=True) -> pd.DataFrame:
    g = pd.read_parquet(DATA_PROCESSED / "gaez_suitability.parquet")
    p = pd.read_parquet(ARTIFACTS / f"loss_predictions_areas_{VERSION}.parquet")
    info = p.drop_duplicates("area_id").set_index("area_id")[["kind", "name", "province"]]
    piv = p.pivot_table(index="area_id", columns="scenario_id", values="loss_pct").join(info).reset_index()
    prob = p[p.scenario_id == "nino_extremo"].set_index("area_id").prob_loss_gt20
    ann = p[p.scenario_id == "ssp585_2050"].set_index("area_id")
    prov = pd.read_csv(ARTIFACTS.parent / "data" / "provinces_supabase.csv", dtype=str)
    key = dict(zip(prov.id, prov.model_name.fillna(prov.name)))
    piv["gaez_key"] = np.where(piv.kind == "canton", piv.area_id, piv.area_id.map(key))
    df = piv.merge(g, left_on="gaez_key", right_on="area_name", how="left")
    df = df.assign(prob_loss_gt20_nino_extremo=df.area_id.map(prob),
                   annual_loss_pct_today=df.area_id.map(ann.get("annual_loss_pct_today")),
                   annual_loss_pct_2050_freq_x2=df.area_id.map(ann.get("annual_loss_pct_2050_freq_x2")))
    df["zone_2050"] = [zone(s, r) for s, r in zip(df.si_2050_rcp85_alto, df.nino_extremo)]
    df["zone_today"] = [zone(s, r) for s, r in zip(df.si_hoy_alto, df.nino_extremo)]
    df["recomendacion"] = df.zone_2050.map(ACTION)
    cols = ["area_id", "kind", "name", "province", "zone_today", "zone_2050", "recomendacion",
            "nino_extremo", "actual", "normal", "prob_loss_gt20_nino_extremo", "annual_loss_pct_today",
            "annual_loss_pct_2050_freq_x2", "si_hoy_alto", "si_hoy_bajo", "si_2050_rcp45_alto", "si_2050_rcp85_alto",
            "clase_hoy_alto", "clase_2050_rcp85_alto", "cambio_2050_rcp45_pct", "cambio_2050_rcp85_pct"]
    out = df[cols].rename(columns={"nino_extremo": "loss_pct_nino_extremo", "actual": "loss_pct_actual",
                                   "normal": "loss_pct_normal"})
    out.round(3).to_csv(f"{OUT}.csv", index=False)
    out.round(3).to_parquet(f"{OUT}.parquet", index=False)
    if verbose:
        c = out[out.kind == "canton"]
        print("Cantones por zona (2050):", c.zone_2050.value_counts().to_dict(), "| hoy:", c.zone_today.value_counts().to_dict())
        print(out[out.kind != "canton"][["name", "zone_2050", "loss_pct_nino_extremo", "si_hoy_alto", "si_2050_rcp85_alto",
                                         "cambio_2050_rcp85_pct"]].round(1).to_string(index=False))
        print("\nZona 'manejo' (apta y muy expuesta), top 10 por pérdida:")
        print(c[c.zone_2050 == "manejo"].nlargest(10, "loss_pct_nino_extremo")[
            ["name", "province", "loss_pct_nino_extremo", "si_2050_rcp85_alto"]].round(1).to_string(index=False))
        print(f"\nGuardado: {OUT}.csv/.parquet")
    return out


if __name__ == "__main__":
    run()
