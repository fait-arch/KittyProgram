"""Predicciones del modelo entrenado (ml/artifacts, rama de ML) como respaldo de la base.

Mientras `loss_predictions` no tenga filas de un escenario en Supabase, el backend sirve las del
artefacto del modelo (`ml/artifacts/loss_predictions_v1.csv` + `model_version_v1.json`):

- Provincias: el valor del modelo tal cual (pérdida, intervalo p10–p90, toneladas, USD, factores).
- Cantones: heredan el índice de su provincia (el modelo se entrena por provincia). Se marcan
  `evidence = indice_subnacional_no_validado` y `inherited_from = <provincia>`; sin toneladas ni USD,
  porque no hay hectáreas de cacao medidas por cantón.
- Cantones de provincias que el modelo no cubre (Amazonía, Sierra): sin fila → "sin estimación".

En cuanto la base tenga predicciones para un escenario, se usan las de la base y esto no actúa.
"""
from __future__ import annotations

import csv
import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Any

from ..core.config import BACK_DIR, get_settings
from .common import name_key

log = logging.getLogger(__name__)

# Textos para los escenarios que solo existen en el modelo (no están en la tabla scenarios)
EXTRA_SCENARIOS = {
    "nino_extremo": {"name_es": "Niño costero extremo", "kind": "historical", "phase": 1, "period_start": 1983,
                     "period_end": 1998, "ssp": None,
                     "description": "Un Niño costero como 1983 o 1998: lluvia extrema en la Costa durante meses."},
}


def _path(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else (BACK_DIR / q).resolve()


def _f(v: Any) -> float | None:
    try:
        return None if v in (None, "", "nan") else float(v)
    except ValueError:
        return None


class ModelArtifacts:
    """Lee una sola vez el CSV de predicciones y la ficha del modelo."""

    def __init__(self) -> None:
        s = get_settings()
        self.csv_path = _path(s.ml_predictions_path)
        self.card_path = _path(s.ml_model_card_path)

    @cached_property
    def rows(self) -> list[dict]:
        if not self.csv_path.exists():
            log.info("Sin predicciones del modelo en %s", self.csv_path)
            return []
        out: list[dict] = []
        # el CSV principal y los complementarios (p. ej. loss_predictions_2050_v1.csv de build_predictions.py)
        extra = sorted(p for p in self.csv_path.parent.glob("loss_predictions_*.csv") if p != self.csv_path)
        for path in [self.csv_path, *extra]:
            with path.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            out.extend(rows)
            log.info("Predicciones del modelo: %d filas de %s", len(rows), path.name)
        return out

    @cached_property
    def card(self) -> dict | None:
        if not self.card_path.exists():
            return None
        return json.loads(self.card_path.read_text(encoding="utf-8"))

    @cached_property
    def by_area(self) -> dict[tuple[str, str, str], dict]:
        """(crop, escenario, nombre normalizado) → fila"""
        return {(r.get("crop_id") or "cacao", r["scenario_id"], name_key(r["area_name"])): r for r in self.rows}

    def scenarios(self, crop: str) -> set[str]:
        return {r["scenario_id"] for r in self.rows if (r.get("crop_id") or "cacao") == crop}

    def get(self, crop: str, scenario: str, area_name: str) -> dict | None:
        return self.by_area.get((crop, scenario, name_key(area_name)))

    def model(self, crop: str) -> dict | None:
        c = self.card
        if not c or c.get("crop_id", "cacao") != crop:
            return None
        return {"id": c["name"], "name": c["name"], "crop_id": crop, "algorithm": c.get("algorithm"),
                "target": c.get("target"), "features": c.get("features"), "metrics": c.get("metrics") or {},
                "train_start_year": c.get("train_start_year"), "train_end_year": c.get("train_end_year"),
                "n_samples": c.get("n_samples"), "is_active": True, "origin": "ml/artifacts",
                "created_at": c.get("created_at")}


class ArtifactBackedSource:
    """Envuelve la fuente de datos: todo igual, salvo pérdidas/modelo cuando la base no los tiene."""

    def __init__(self, base) -> None:
        self.base = base
        self.art = ModelArtifacts()

    def __getattr__(self, name: str):
        return getattr(self.base, name)

    # ── catálogo ──
    def scenarios(self) -> list[dict]:
        rows = list(self.base.scenarios())
        have = {r["id"] for r in rows}
        for sid in sorted(self.art.scenarios("cacao") - have):
            if sid in EXTRA_SCENARIOS:
                rows.append({"id": sid, **EXTRA_SCENARIOS[sid]})
        return rows

    def active_model(self, crop: str) -> dict | None:
        m = self.base.active_model(crop)
        if m and self._db_has_losses(crop):
            return m
        return self.art.model(crop) or m

    def available_scenarios(self, crop: str) -> set[str]:
        return set(self.base.available_scenarios(crop)) | self.art.scenarios(crop)

    def _db_has_losses(self, crop: str) -> bool:
        try:
            return bool(self.base.available_scenarios(crop))
        except Exception:  # noqa: BLE001
            return False

    # ── pérdidas ──
    def _provinces(self) -> dict[str, dict]:
        return {p["id"]: p for p in self.base.areas("province")}

    def _row(self, area: dict, prov: dict | None, pred: dict, scenario: str, crop: str, inherited: bool) -> dict:
        factors = pred.get("top_factors")
        try:
            factors = json.loads(factors) if isinstance(factors, str) and factors else factors
        except json.JSONDecodeError:
            factors = []
        row = {
            "area_id": area["id"], "name": area["name"], "kind": area["kind"], "region": area.get("region"),
            "province": (prov or {}).get("name") if area["kind"] == "canton" else "Ecuador",
            "area_ha": _f(area.get("area_ha")), "crop_id": crop, "scenario_id": scenario,
            "loss_pct": _f(pred.get("loss_pct")), "loss_pct_low": _f(pred.get("loss_pct_low")),
            "loss_pct_high": _f(pred.get("loss_pct_high")),
            "exposed_ha": None if inherited else _f(pred.get("exposed_ha")),
            "loss_t": None if inherited else _f(pred.get("loss_t")),
            "loss_usd": None if inherited else _f(pred.get("loss_usd")),
            "expected_yield_t_ha": _f(pred.get("expected_yield_t_ha")),
            "price_usd_t": _f(pred.get("price_usd_t")),
            "risk_class": pred.get("risk_class") or None,
            "top_factors": factors or [],
            "model_name": pred.get("model_version"),
            "evidence": "indice_subnacional_no_validado" if inherited else pred.get("evidence"),
            "extrapolated": str(pred.get("extrapolated", "")).lower() == "true",
            "prob_loss_gt20": _f(pred.get("prob_loss_gt20")),
            "inherited_from": (prov or {}).get("name") if inherited else None,
            "scenario_years": pred.get("scenario_years"),
        }
        return row

    def _artifact_losses(self, crop: str, scenario: str, kind: str | None, province: str | None,
                         area_id: str | None) -> list[dict]:
        if scenario not in self.art.scenarios(crop):
            return []
        provs = self._provinces()
        prov_keys = {name_key(p["name"]) for p in provs.values()} | {"national"}
        out = []
        kinds = [kind] if kind else ["province", "canton"]
        for k in kinds:
            for a in self.base.areas(k):
                if area_id and a["id"] != area_id:
                    continue
                if k == "province":
                    pred = self.art.get(crop, scenario, a["name"])
                    if pred and (not province or name_key(province) == name_key(a["name"])):
                        out.append(self._row(a, None, pred, scenario, crop, inherited=False))
                else:
                    prov = provs.get(a.get("parent_id"))
                    if not prov or (province and name_key(province) != name_key(prov["name"])):
                        continue
                    # si ML ya calculó el cantón (y no es un cantón homónimo de su provincia: Esmeraldas, Guayas…)
                    own = None if name_key(a["name"]) in prov_keys else self.art.get(crop, scenario, a["name"])
                    pred = own or self.art.get(crop, scenario, prov["name"])
                    if pred:
                        out.append(self._row(a, prov, pred, scenario, crop, inherited=own is None))
        return out

    def losses(self, crop: str, scenario: str | None = None, kind: str | None = None, province: str | None = None,
               area_id: str | None = None, with_geom: bool = False) -> list[dict]:
        rows = self.base.losses(crop, scenario=scenario, kind=kind, province=province, area_id=area_id,
                                with_geom=with_geom)
        if rows or not scenario:
            return rows
        rows = self._artifact_losses(crop, scenario, kind, province, area_id)
        if with_geom and rows:
            geoms = {g["id"]: g["geom"] for k in {r["kind"] for r in rows} for g in self.base.areas_geom(k)}
            for r in rows:
                r["geom"] = geoms.get(r["area_id"])
        return rows

    def zones(self, crop: str, future: str) -> list[dict]:
        """Zonas 2050: la base las calcula por provincia (parte 10); cada cantón hereda la de su provincia."""
        rows = list(self.base.zones(crop, future))
        have = {r["area_id"] for r in rows}
        provs = self._provinces()
        cantons_by_prov: dict[str, list[dict]] = {}
        for c in self.base.areas("canton"):
            cantons_by_prov.setdefault(c.get("parent_id"), []).append(c)
        extra = []
        for r in rows:
            if r["area_id"] not in provs:
                continue
            for c in cantons_by_prov.get(r["area_id"], []):
                if c["id"] not in have:
                    extra.append({**r, "area_id": c["id"], "areas": {"name": c["name"], "parent_id": c.get("parent_id")},
                                  "inherited_from": provs[r["area_id"]]["name"]})
        return rows + extra

    def loss_full(self, model_version_id: str, area_id: str, crop: str, scenario: str) -> dict | None:
        art_model = (self.art.card or {}).get("name")
        if model_version_id != art_model:          # id del modelo de la base (uuid)
            row = self.base.loss_full(model_version_id, area_id, crop, scenario)
            if row:
                return row
        hit = self._artifact_losses(crop, scenario, None, None, area_id)
        return hit[0] if hit else None
