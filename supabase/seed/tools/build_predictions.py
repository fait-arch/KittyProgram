"""Predicciones del modelo de ML → SQL para loss_predictions (parte 13 del seed).

Uso (desde la raíz del repo, con el entorno de ml/: scikit-learn 1.9.1, pandas, pyarrow):

    python supabase/seed/tools/build_predictions.py \
        --territorio supabase/seed/data/01_territorio.sql \
        --deltas     supabase/seed/data/10_proyecciones_2050.sql \
        --out        supabase/seed/data/13_predicciones_modelo.sql

Qué genera:
  1. model_versions: la ficha de ml/artifacts/model_version_v1.json (id fijo), activa; desactiva las demás de cacao.
  2. scenarios: 'nino_extremo' (Niño costero como 1983/1998), que solo existe en el modelo.
  3. loss_predictions, para Ecuador, las provincias del modelo y sus cantones:
     - normal, nino, nina, nino_extremo, actual: tal cual ml/artifacts/loss_predictions_v1.csv.
     - ssp245_2050 / ssp585_2050: método delta sobre la salida del modelo:
           2050 = CSV(normal) + [predict(normal + Δclima 2050) − predict(normal)]
       con Δclima = deltas mensuales ene–jun de NASA NEX-GDDP-CMIP6 por provincia (parte 10:
       temperatura aditiva, lluvia relativa), aplicados con ml.inference.adjust_features (las mismas
       pendientes históricas que usan los sliders del what-if). Se marcan extrapolated = true.
     - Cantones: heredan el índice de su provincia (el modelo se entrena por provincia):
       evidence = 'indice_subnacional_no_validado', inherited_from_area_id = provincia, sin t ni USD.
Requiere la migración 0010_modelo_ml.sql (columnas evidence, extrapolated, prob_loss_gt20, inherited_from_area_id).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCEN_2050 = ["ssp245_2050", "ssp585_2050"]
CLASSES = [(5, "bajo"), (15, "medio"), (30, "alto")]          # = BACK/app/services/labels.RISK_CLASSES
MODEL_NS = uuid.UUID("6f1c2b8e-0c39-4c55-9a0e-7d1f3c0f5a10")


def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def risk_class(p: float) -> str:
    return next((c for top, c in CLASSES if p < top), "muy_alto")


def q(v) -> str:
    if v is None or v == "":
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(float(v), 4))
    return "'" + str(v).replace("'", "''") + "'"


def read_areas(path: Path) -> list[dict]:
    rx = re.compile(r"\('([0-9a-f-]{36})','(country|province|canton)','((?:[^']|'')*)',(NULL|'[0-9a-f-]{36}')")
    return [{"id": i, "kind": k, "name": n.replace("''", "'"), "parent": None if p == "NULL" else p.strip("'")}
            for i, k, n, p in rx.findall(path.read_text(encoding="utf-8"))]


def read_deltas(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    """(province_id, escenario) → {'tas': °C, 'pr': %} promedio ene–jun."""
    s = path.read_text(encoding="utf-8")
    blk = s[s.index("insert into _delta values"):]
    blk = blk[:blk.index(";")]
    acc: dict[tuple[str, str, str], list[float]] = {}
    for pid, sc, m, var, mean, *_ in re.findall(
            r"\('([0-9a-f-]{36})','(\w+)',(\d+),'(\w+)',([-\d.]+),([-\d.]+),([-\d.]+),(\d+)\)", blk):
        if int(m) <= 6 and var in ("tas", "pr"):
            acc.setdefault((pid, sc, var), []).append(float(mean))
    out: dict[tuple[str, str], dict[str, float]] = {}
    for (pid, sc, var), vals in acc.items():
        out.setdefault((pid, sc), {})[var] = sum(vals) / len(vals)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--territorio", type=Path, default=ROOT / "supabase/seed/data/01_territorio.sql")
    ap.add_argument("--deltas", type=Path, default=ROOT / "supabase/seed/data/10_proyecciones_2050.sql")
    ap.add_argument("--ml", type=Path, default=ROOT / "ml", help="carpeta ml/ (código + artifacts/)")
    ap.add_argument("--out", type=Path, default=ROOT / "supabase/seed/data/13_predicciones_modelo.sql")
    ap.add_argument("--csv-2050", type=Path, default=None,
                    help="CSV con las filas 2050 (mismo formato que loss_predictions_v1.csv); por defecto en ml/artifacts/")
    a = ap.parse_args()

    sys.path.insert(0, str(a.ml.parent))
    import joblib
    from ml import inference as inf

    art = a.ml / "artifacts"
    card = json.loads((art / "model_version_v1.json").read_text(encoding="utf-8"))
    bundle = joblib.load(art / "cacao_loss_v1.joblib")
    preds = list(csv.DictReader((art / "loss_predictions_v1.csv").open(encoding="utf-8")))
    areas = read_areas(a.territorio)
    deltas = read_deltas(a.deltas)

    country = next(x for x in areas if x["kind"] == "country")
    provs = {key(x["name"]): x for x in areas if x["kind"] == "province"}
    model_id = str(uuid.uuid5(MODEL_NS, card["name"]))

    # filas del CSV por (área, escenario)
    by: dict[tuple[str, str], dict] = {}
    for r in preds:
        area = country if r["area_name"] == "national" else provs.get(key(r["area_name"]))
        if not area:
            print(f"  ⚠ área del modelo sin match en la base: {r['area_name']}")
            continue
        by[(area["id"], r["scenario_id"])] = {**r, "_area": area}

    # 2050 por método delta
    model_areas = {r["_area"]["id"]: r for (aid, sc), r in by.items() if sc == "normal"}
    for aid, base in model_areas.items():
        name = base["area_name"]
        feats = bundle["scenario_features"].get(name, {}).get("normal")
        if not feats:
            print(f"  ⚠ sin features 'normal' en el bundle para {name}")
            continue
        p0 = inf.predict(bundle, feats)
        for sc in SCEN_2050:
            if aid == country["id"]:      # nacional: delta promedio ponderado por hectáreas de las provincias
                w = [(float(model_areas[p]["exposed_ha"] or 0), deltas.get((p, sc))) for p in model_areas if p != aid]
                w = [(h, d) for h, d in w if d and h]
                tot = sum(h for h, _ in w) or 1
                d = {v: sum(h * dd[v] for h, dd in w) / tot for v in ("tas", "pr")}
            else:
                d = deltas.get((aid, sc))
            if not d:
                print(f"  ⚠ sin delta CMIP6 para {name} {sc}")
                continue
            f2 = inf.adjust_features(feats, {"temp_delta_c": d["tas"], "rain_delta_pct": d["pr"]})
            p1 = inf.predict(bundle, f2)
            shift = p1["loss_pct"] - p0["loss_pct"]
            clip = lambda v: max(0.0, min(100.0, v))  # noqa: E731
            pct = clip(float(base["loss_pct"]) + shift)
            ha, yld, price = (float(base[k]) if base[k] else None for k in ("exposed_ha", "expected_yield_t_ha", "price_usd_t"))
            loss_t = ha * yld * pct / 100 if ha and yld else None
            by[(aid, sc)] = {**base, "scenario_id": sc, "loss_pct": pct,
                             "loss_pct_low": clip(float(base["loss_pct_low"]) + shift),
                             "loss_pct_high": clip(float(base["loss_pct_high"]) + shift),
                             "loss_t": loss_t, "loss_usd": loss_t * price if loss_t and price else None,
                             "risk_class": risk_class(pct), "top_factors": json.dumps(p1["top_factors"]),
                             "extrapolated": "True", "_delta": d}
            print(f"  {name:32} {sc}: Δt {d['tas']:+.2f} °C, Δlluvia {d['pr']:+.1f} % → {pct:5.1f} % (normal {float(base['loss_pct']):.1f})")

    # CSV 2050 para el respaldo del backend (BACK/app/data/model_artifacts.py) mientras la base no tenga filas
    out_csv = a.csv_2050 or (art / "loss_predictions_2050_v1.csv")
    header = list(preds[0].keys())
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for (aid, sc), r in by.items():
            if sc in SCEN_2050:
                w.writerow({**r, "scenario_years": "[2041, 2060]",
                            "loss_t": "" if r["loss_t"] is None else round(r["loss_t"], 1),
                            "loss_usd": "" if r["loss_usd"] is None else round(r["loss_usd"])})
    print(f"{out_csv}: filas 2050 para el respaldo del backend")

    cols = ["model_version_id", "area_id", "crop_id", "scenario_id", "loss_pct", "loss_pct_low", "loss_pct_high",
            "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd", "risk_class", "top_factors",
            "evidence", "extrapolated", "prob_loss_gt20", "inherited_from_area_id"]
    values = []
    for (aid, sc), r in sorted(by.items(), key=lambda kv: (kv[1]["_area"]["kind"], kv[1]["_area"]["name"], kv[0][1])):
        row = [model_id, aid, "cacao", sc, float(r["loss_pct"]), float(r["loss_pct_low"]), float(r["loss_pct_high"]),
               r["exposed_ha"], r["expected_yield_t_ha"], r["loss_t"], r["price_usd_t"], r["loss_usd"], r["risk_class"],
               r["top_factors"], r.get("evidence") or None, str(r.get("extrapolated")).lower() == "true",
               r.get("prob_loss_gt20") or None, None]
        values.append(row)
        if r["_area"]["kind"] == "province":          # cantones de la provincia: heredan el índice
            for c in (x for x in areas if x["kind"] == "canton" and x["parent"] == aid):
                values.append([model_id, c["id"], "cacao", sc, row[4], row[5], row[6], None, r["expected_yield_t_ha"],
                               None, r["price_usd_t"], None, r["risk_class"], r["top_factors"],
                               "indice_subnacional_no_validado", row[15], row[16], aid])

    num = lambda v: None if v in (None, "") else float(v)  # noqa: E731
    lines = [
        "-- 13 — Predicciones del modelo de ML (cacao_loss_v1) para el mapa, por escenario.",
        "-- Generado por supabase/seed/tools/build_predictions.py desde ml/artifacts (rama beltranfuego) y la parte 10 (CMIP6).",
        "-- Requiere supabase/migrations/0010_modelo_ml.sql. Idempotente: se puede volver a correr.",
        "begin;",
        "",
        "insert into public.scenarios (id, name_es, kind, phase, period_start, period_end, ssp, description) values",
        "('nino_extremo', 'Niño costero extremo', 'historical', 1, 1983, 1998, null, "
        "'Un Niño costero como 1983 o 1998: lluvia extrema en la Costa durante meses.')",
        "on conflict (id) do update set name_es = excluded.name_es, description = excluded.description;",
        "",
        f"update public.model_versions set is_active = false where crop_id = 'cacao' and id <> {q(model_id)};",
        "insert into public.model_versions (id, name, crop_id, target, algorithm, features, hyperparams, cv_scheme, metrics,",
        "  train_start_year, train_end_year, n_samples, artifact_path, is_active) values (",
        f"  {q(model_id)}, {q(card['name'])}, 'cacao', {q(card['target'])}, {q(card['algorithm'])},",
        f"  array[{', '.join(q(f) for f in card['features'])}]::text[], {q(json.dumps(card.get('hyperparams')))}::jsonb, {q(card.get('cv_scheme'))},",
        f"  {q(json.dumps(card.get('metrics')))}::jsonb, {card.get('train_start_year') or 'null'}, {card.get('train_end_year') or 'null'},",
        f"  {card.get('n_samples') or 'null'}, {q(card.get('artifact_path'))}, true)",
        "on conflict (id) do update set metrics = excluded.metrics, features = excluded.features, is_active = true;",
        "",
        f"delete from public.loss_predictions where model_version_id = {q(model_id)};",
        f"insert into public.loss_predictions ({', '.join(cols)}) values",
    ]
    body = []
    for v in values:
        v = list(v)
        for i in (7, 8, 9, 10, 11, 16):
            v[i] = num(v[i])
        cells = [q(x) for x in v]
        cells[13] = f"{q(v[13])}::jsonb" if v[13] else "null"
        body.append("(" + ", ".join(cells) + ")")
    lines.append(",\n".join(body) + ";")
    lines += ["", "commit;", ""]
    a.out.write_text("\n".join(lines), encoding="utf-8")
    n_c = sum(1 for v in values if v[17])
    print(f"\n{a.out}: {len(values)} filas ({len(values) - n_c} Ecuador/provincias, {n_c} cantones), modelo {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
