"""Predicciones del modelo POR ÁREA (país, provincias y cantones) → SQL para loss_predictions (parte 13).

Usa ml/artifacts/loss_predictions_areas_v1.csv del equipo de ML (rama beltranfuego), que ya trae:
  - area_id = uuid de la tabla `areas` de Supabase (país, 6 provincias de la Costa y 125 cantones),
  - 7 escenarios: normal, nino, nina, nino_extremo, actual, ssp245_2050 y ssp585_2050 (2050 con CMIP6),
  - prob_loss_gt20, exposición (ha), toneladas y USD por cantón.

    python supabase/seed/tools/build_predictions_areas.py          # → supabase/seed/data/13_predicciones_modelo.sql

Lo que completa este script:
  1. Provincias sin fila propia (las 6 de la Amazonía): se agregan desde sus cantones
     (% ponderado por hectáreas, t y USD sumados), evidence 'indice_subnacional_no_validado', extrapolated = true.
  2. Cantones de la base sin predicción (p. ej. Logroño, sin polígono en GAUL 2015): heredan su provincia
     (inherited_from_area_id), sin t ni USD.
Reemplaza a la versión anterior (cantones heredando la provincia) y a la parte 14 (Amazonía desde Sucumbíos).
Requiere la migración 0010_modelo_ml.sql.
"""
from __future__ import annotations

import argparse
import csv
import json
import uuid
from collections import defaultdict
from pathlib import Path

from build_predictions import MODEL_NS, q, read_areas, risk_class

ROOT = Path(__file__).resolve().parents[3]
SCEN = ["normal", "nino", "nina", "nino_extremo", "actual", "ssp245_2050", "ssp585_2050"]
COLS = ["model_version_id", "area_id", "crop_id", "scenario_id", "loss_pct", "loss_pct_low", "loss_pct_high",
        "exposed_ha", "expected_yield_t_ha", "loss_t", "price_usd_t", "loss_usd", "risk_class", "top_factors",
        "evidence", "extrapolated", "prob_loss_gt20", "inherited_from_area_id"]


def num(v):
    return None if v in (None, "", "nan", "None") else float(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--territorio", type=Path, default=ROOT / "supabase/seed/data/01_territorio.sql")
    ap.add_argument("--ml", type=Path, default=ROOT / "ml")
    ap.add_argument("--out", type=Path, default=ROOT / "supabase/seed/data/13_predicciones_modelo.sql")
    a = ap.parse_args()

    art = a.ml / "artifacts"
    card = json.loads((art / "model_version_v1.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((art / "loss_predictions_areas_v1.csv").open(encoding="utf-8")))
    areas = read_areas(a.territorio)
    by_id = {x["id"]: x for x in areas}
    model_id = str(uuid.uuid5(MODEL_NS, card["name"]))

    vals: dict[tuple[str, str], list] = {}
    skipped = set()
    for r in rows:
        if r["area_id"] not in by_id:
            skipped.add(r["name"]); continue
        if r["scenario_id"] not in SCEN:
            continue
        pct = num(r["loss_pct"])
        vals[(r["area_id"], r["scenario_id"])] = [
            model_id, r["area_id"], "cacao", r["scenario_id"], pct, num(r["loss_pct_low"]), num(r["loss_pct_high"]),
            num(r["exposed_ha"]), num(r["expected_yield_t_ha"]), num(r["loss_t"]), num(r["price_usd_t"]), num(r["loss_usd"]),
            r["risk_class"] or risk_class(pct), r["top_factors"] or None, r["evidence"] or None,
            str(r["extrapolated"]).lower() == "true", num(r["prob_loss_gt20"]), None]
    if skipped:
        print(f"  ⚠ áreas del modelo sin match en la base: {', '.join(sorted(skipped))}")

    # 1. Provincias sin fila: agregadas desde sus cantones
    cantons_of = defaultdict(list)
    for x in areas:
        if x["kind"] == "canton":
            cantons_of[x["parent"]].append(x["id"])
    added_p = []
    for p in (x for x in areas if x["kind"] == "province"):
        for sc in SCEN:
            if (p["id"], sc) in vals:
                continue
            cs = [vals[(c, sc)] for c in cantons_of[p["id"]] if (c, sc) in vals]
            if not cs:
                continue
            w = [(c[7] or 0.0) for c in cs]
            tw = sum(w) or len(cs)
            wavg = lambda i: sum((c[i] or 0.0) * (wi if sum(w) else 1) for c, wi in zip(cs, w)) / tw  # noqa: E731
            pct = wavg(4)
            probs = [c[16] for c in cs if c[16] is not None]
            tsum = sum(c[9] for c in cs if c[9] is not None) if any(c[9] is not None for c in cs) else None
            usum = sum(c[11] for c in cs if c[11] is not None) if any(c[11] is not None for c in cs) else None
            ha = sum(w) or None
            vals[(p["id"], sc)] = [model_id, p["id"], "cacao", sc, pct, wavg(5), wavg(6), ha,
                                   (tsum / (ha * pct / 100)) if tsum and ha and pct else cs[0][8], tsum, cs[0][10], usum,
                                   risk_class(pct), cs[0][13], cs[0][14], True,
                                   wavg(16) if probs else None, None]
            added_p.append(p["name"])

    # 2. Cantones sin predicción: heredan la provincia
    added_c = []
    for c in (x for x in areas if x["kind"] == "canton"):
        for sc in SCEN:
            pv = vals.get((c["parent"], sc))
            if (c["id"], sc) in vals or not pv:
                continue
            vals[(c["id"], sc)] = [model_id, c["id"], "cacao", sc, pv[4], pv[5], pv[6], None, pv[8], None, pv[10], None,
                                   pv[12], pv[13], "indice_subnacional_no_validado", pv[15], pv[16], c["parent"]]
            added_c.append(c["name"])

    order = {"country": 0, "province": 1, "canton": 2}
    values = sorted(vals.values(), key=lambda v: (order[by_id[v[1]]["kind"]], by_id[v[1]]["name"], SCEN.index(v[3])))
    body = []
    for v in values:
        cells = [q(x) for x in v]
        cells[13] = f"{q(v[13])}::jsonb" if v[13] else "null"
        body.append("(" + ", ".join(cells) + ")")

    lines = [
        "-- 13 — Predicciones del modelo de ML (cacao_loss_v1) por país, provincia y CANTÓN, 7 escenarios.",
        "-- Generado por supabase/seed/tools/build_predictions_areas.py desde ml/artifacts/loss_predictions_areas_v1.csv",
        "-- (rama beltranfuego: clima propio de cada cantón, 2050 con CMIP6, probabilidad de año malo).",
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
        f"insert into public.loss_predictions ({', '.join(COLS)}) values",
        ",\n".join(body) + ";",
        "",
        "commit;",
        "",
    ]
    a.out.write_text("\n".join(lines), encoding="utf-8")
    kinds = defaultdict(int)
    for v in values:
        kinds[by_id[v[1]]["kind"]] += 1
    print(f"{a.out}: {len(values)} filas · {dict(kinds)}")
    if added_p:
        print(f"  provincias agregadas desde sus cantones: {', '.join(sorted(set(added_p)))}")
    if added_c:
        print(f"  cantones que heredan su provincia: {', '.join(sorted(set(added_c)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
