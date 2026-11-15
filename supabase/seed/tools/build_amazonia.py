"""Predicciones para la Amazonía → SQL (parte 14 del seed, va DESPUÉS de la 13).

El modelo cacao_loss_v1 se publicó solo para las 6 provincias de la Costa, pero su bundle trae el
clima de los escenarios de Sucumbíos (única provincia amazónica con datos de entrenamiento).

    python supabase/seed/tools/build_amazonia.py            # escribe 14_predicciones_amazonia.sql

Método (todo marcado extrapolated = true y evidence = 'indice_subnacional_no_validado'):
  1. Sucumbíos, escenarios históricos: predict(bundle, features medias del escenario) + calibración.
     La tabla publicada (ml.predict) promedia la predicción AÑO por AÑO; con las features medias el
     modelo (con bisagra de lluvia) da menos. La calibración suma, por escenario, la diferencia media
     tabla − predicción observada en las 6 provincias de la Costa. Recortado a 0–100.
  2. Napo, Orellana, Pastaza, Morona Santiago y Zamora Chinchipe: heredan el índice de Sucumbíos
     (misma región climática; inherited_from_area_id = Sucumbíos).
  3. 2050 (SSP2-4.5 / SSP5-8.5), por provincia: valor normal + [predict(normal + Δclima de ESA provincia)
     − predict(normal)], con los deltas NASA NEX-GDDP-CMIP6 de la parte 10 (igual que la parte 13).
  4. Toneladas y USD: hectáreas de cacao de ESPAC (crop_exposure, parte 05) × rendimiento esperado
     nacional del modelo × precio del modelo. Los cantones heredan el % de su provincia, sin t ni USD.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_predictions import MODEL_NS, key, q, read_areas, read_deltas, risk_class  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
HIST = ["normal", "nino", "nina", "nino_extremo", "actual"]
SCEN_2050 = ["ssp245_2050", "ssp585_2050"]
AMAZONIA = ["Sucumbios", "Napo", "Orellana", "Pastaza", "Morona Santiago", "Zamora Chinchipe"]
SOURCE = "Sucumbios"


def read_exposure(path: Path) -> dict[str, float]:
    s = path.read_text(encoding="utf-8")
    blk = s[s.index("insert into public.crop_exposure"):]
    blk = blk[:blk.index(";")]
    out: dict[str, float] = {}
    for aid, ha, method in re.findall(r"\('([0-9a-f-]{36})','cacao',\d+,([-\d.]+),'(\w+)'", blk):
        if method == "espac_direct":
            out[aid] = float(ha)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "supabase/seed/data")
    ap.add_argument("--ml", type=Path, default=ROOT / "ml")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    out = a.out or a.data / "14_predicciones_amazonia.sql"

    sys.path.insert(0, str(a.ml.parent))
    import joblib
    from ml import inference as inf

    art = a.ml / "artifacts"
    card = json.loads((art / "model_version_v1.json").read_text(encoding="utf-8"))
    bundle = joblib.load(art / "cacao_loss_v1.joblib")
    table = list(csv.DictReader((art / "loss_predictions_v1.csv").open(encoding="utf-8")))
    areas = read_areas(a.data / "01_territorio.sql")
    deltas = read_deltas(a.data / "10_proyecciones_2050.sql")
    exposure = read_exposure(a.data / "05_produccion_y_precios.sql")
    model_id = str(uuid.uuid5(MODEL_NS, card["name"]))
    provs = {key(x["name"]): x for x in areas if x["kind"] == "province"}
    nat = next(r for r in table if r["area_name"] == "national" and r["scenario_id"] == "normal")
    yld, price = float(nat["expected_yield_t_ha"]), float(nat["price_usd_t"])
    clip = lambda v: max(0.0, min(100.0, v))  # noqa: E731

    # 1. calibración por escenario: tabla publicada − predicción con features medias (provincias de la Costa)
    offset: dict[str, float] = {}
    for sc in HIST:
        diffs = []
        for r in table:
            f = bundle["scenario_features"].get(r["area_name"], {}).get(sc)
            if r["scenario_id"] == sc and r["area_name"] != "national" and f:
                diffs.append(float(r["loss_pct"]) - inf.predict(bundle, f)["loss_pct"])
        offset[sc] = sum(diffs) / len(diffs)

    src = provs[key(SOURCE)]
    base: dict[str, dict] = {}
    for sc in HIST:
        p = inf.predict(bundle, bundle["scenario_features"][SOURCE][sc])
        sh = offset[sc]
        base[sc] = {"loss_pct": clip(p["loss_pct"] + sh), "low": clip(p["loss_pct_low"] + sh if p["loss_pct_low"] else 0),
                    "high": clip(p["loss_pct_high"] + sh), "top_factors": p["top_factors"]}
        print(f"  Sucumbíos {sc:13} modelo {p['loss_pct']:5.1f} % + calibración {sh:+5.1f} → {base[sc]['loss_pct']:5.1f} %")

    feats0 = bundle["scenario_features"][SOURCE]["normal"]
    p0 = inf.predict(bundle, feats0)["loss_pct"]
    rows = []   # (area, scenario, pct, low, high, factors, inherited_from_id)
    for name in AMAZONIA:
        prov = provs.get(key(name))
        if not prov:
            print(f"  ⚠ {name} no está en la base")
            continue
        inh = None if prov["id"] == src["id"] else src["id"]
        for sc in HIST:
            b = base[sc]
            rows.append((prov, sc, b["loss_pct"], b["low"], b["high"], b["top_factors"], inh))
        for sc in SCEN_2050:
            d = deltas.get((prov["id"], sc))
            if not d:
                print(f"  ⚠ sin delta CMIP6 para {name} {sc}")
                continue
            p1 = inf.predict(bundle, inf.adjust_features(feats0, {"temp_delta_c": d["tas"], "rain_delta_pct": d["pr"]}))
            shift = p1["loss_pct"] - p0
            b = base["normal"]
            rows.append((prov, sc, clip(b["loss_pct"] + shift), clip(b["low"] + shift), clip(b["high"] + shift), p1["top_factors"], None))
            print(f"  {name:18} {sc}: Δt {d['tas']:+.2f} °C, Δlluvia {d['pr']:+.1f} % → {clip(b['loss_pct'] + shift):5.1f} %")

    cols = ["model_version_id", "area_id", "crop_id", "scenario_id", "loss_pct", "loss_pct_low", "loss_pct_high",
            "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd", "risk_class", "top_factors",
            "evidence", "extrapolated", "prob_loss_gt20", "inherited_from_area_id"]
    values = []
    for prov, sc, pct, low, high, factors, inh in rows:
        ha = exposure.get(prov["id"])
        loss_t = ha * yld * pct / 100 if ha else None
        fx = json.dumps(factors)
        values.append([model_id, prov["id"], "cacao", sc, pct, low, high, ha, yld, loss_t, price,
                       loss_t * price if loss_t is not None else None, risk_class(pct), fx,
                       "indice_subnacional_no_validado", True, None, inh])
        for c in (x for x in areas if x["kind"] == "canton" and x["parent"] == prov["id"]):
            values.append([model_id, c["id"], "cacao", sc, pct, low, high, None, yld, None, price, None,
                           risk_class(pct), fx, "indice_subnacional_no_validado", True, None, prov["id"]])

    ids = sorted({v[1] for v in values})
    body = []
    for v in values:
        cells = [q(x) for x in v]
        cells[13] = f"{q(v[13])}::jsonb"
        body.append("(" + ", ".join(cells) + ")")
    lines = [
        "-- 14 — Predicciones del modelo para la Amazonía (extrapolación, ver supabase/seed/tools/build_amazonia.py).",
        "-- Va después de la parte 13 (que borra y vuelve a insertar las filas del modelo). Idempotente.",
        "begin;",
        f"delete from public.loss_predictions where model_version_id = {q(model_id)} and area_id in ({', '.join(q(i) for i in ids)});",
        f"insert into public.loss_predictions ({', '.join(cols)}) values",
        ",\n".join(body) + ";",
        "commit;",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{out}: {len(values)} filas ({len(rows)} provincia×escenario)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
