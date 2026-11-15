"""Lecturas de Supabase (PostgREST). Solo lectura: el backend no modifica el esquema.

Cada método devuelve dicts/listas planas; los servicios no saben de dónde vienen.
"""
import logging
from typing import Any

from ..core.supabase import anon_client, user_client
from .common import name_key, to_geojson

PAGE = 1000  # PostgREST corta en 1000 filas por defecto
log = logging.getLogger(__name__)


class SupabaseSource:
    name = "supabase"

    # ── helpers ───────────────────────────────────────
    @property
    def db(self):
        return anon_client()

    def _all(self, query) -> list[dict]:
        rows: list[dict] = []
        start = 0
        while True:
            chunk = query.range(start, start + PAGE - 1).execute().data or []
            rows.extend(chunk)
            if len(chunk) < PAGE:
                return rows
            start += PAGE

    def ping(self) -> bool:
        self.db.table("scenarios").select("id").limit(1).execute()
        return True

    # ── catálogos ─────────────────────────────────────
    def scenarios(self) -> list[dict]:
        return self.db.table("scenarios").select("*").order("phase").order("id").execute().data

    def crops(self) -> list[dict]:
        return self.db.table("crops").select("*").execute().data

    def crop_requirements(self, crop: str) -> list[dict]:
        return self.db.table("crop_requirements").select("*").eq("crop_id", crop).execute().data

    def pathogens(self, crop: str) -> list[dict]:
        return self.db.table("pathogens").select("*, disease_thresholds(*)").eq("crop_id", crop).execute().data

    def phenology(self, crop: str) -> list[dict]:
        return self.db.table("crop_phenology").select("*").eq("crop_id", crop).execute().data

    def strategies(self) -> list[dict]:
        return self.db.table("adaptation_strategies").select("*").execute().data

    def strategy_effects(self) -> list[dict]:
        return self.db.table("strategy_effects").select("*").execute().data

    def sources(self) -> list[dict]:
        return self.db.table("data_sources").select("*").order("id").execute().data

    def variables(self) -> list[dict]:
        return self.db.table("variables").select("*").order("id").execute().data

    def active_model(self, crop: str) -> dict | None:
        rows = (self.db.table("model_versions").select("*")
                .eq("crop_id", crop).eq("is_active", True).limit(1).execute().data)
        return rows[0] if rows else None

    def latest_price(self, crop: str) -> dict | None:
        rows = (self.db.table("crop_prices").select("*").eq("crop_id", crop)
                .order("month_date", desc=True).limit(12).execute().data)
        if not rows:
            return None
        avg = sum(float(r["price_usd_t"]) for r in rows) / len(rows)
        return {"price_usd_t": avg, "months": len(rows), "last_month": rows[0]["month_date"]}

    # ── ENSO ──────────────────────────────────────────
    def enso_index(self, index_ids: list[str], date_from: str | None, date_to: str | None) -> list[dict]:
        q = self.db.table("enso_index").select("index_id,month_date,value,phase").in_("index_id", index_ids)
        if date_from:
            q = q.gte("month_date", date_from)
        if date_to:
            q = q.lte("month_date", date_to)
        return self._all(q.order("month_date"))

    def enso_latest(self, index_id: str) -> dict | None:
        rows = (self.db.table("enso_index").select("*").eq("index_id", index_id)
                .order("month_date", desc=True).limit(1).execute().data)
        return rows[0] if rows else None

    def enso_events(self) -> list[dict]:
        return self.db.table("enso_events").select("*").order("start_month").execute().data

    def enso_years(self) -> list[dict]:
        return self._all(self.db.table("v_enso_year_class").select("*").order("year"))

    # ── territorio ────────────────────────────────────
    _AREA_COLS = "id,name,kind,parent_id,area_ha,region,inec_dpa_code,name_key"

    def areas(self, kind: str | None = None, parent_id: str | None = None) -> list[dict]:
        q = self.db.table("areas").select(self._AREA_COLS).neq("kind", "field")
        if kind:
            q = q.eq("kind", kind)
        if parent_id:
            q = q.eq("parent_id", parent_id)
        return self._all(q.order("name"))

    def area(self, area_id: str) -> dict | None:
        rows = self.db.table("areas").select(self._AREA_COLS).eq("id", area_id).limit(1).execute().data
        return rows[0] if rows else None

    def find_area(self, kind: str, name: str) -> dict | None:
        rows = (self.db.table("areas").select(self._AREA_COLS).eq("kind", kind)
                .eq("name_key", name_key(name)).limit(1).execute().data)
        return rows[0] if rows else None

    def areas_geom(self, kind: str, parent_id: str | None = None) -> list[dict]:
        q = self.db.table("areas").select("id,name,kind,parent_id,region,geom_simplified").eq("kind", kind)
        if parent_id:
            q = q.eq("parent_id", parent_id)
        rows = self._all(q)
        for r in rows:
            r["geom"] = to_geojson(r.pop("geom_simplified", None))
        return rows

    def static_features(self, area_id: str) -> dict | None:
        rows = self.db.table("area_static_features").select("*").eq("area_id", area_id).limit(1).execute().data
        return rows[0] if rows else None

    def exposure(self, crop: str, area_id: str | None = None) -> list[dict]:
        q = self.db.table("crop_exposure").select("*").eq("crop_id", crop)
        if area_id:
            q = q.eq("area_id", area_id)
        return self._all(q.order("ref_year", desc=True))

    # ── clima y riesgo ────────────────────────────────
    def scenario_climate(self, area_id: str, scenario: str, variables: list[str] | None = None) -> list[dict]:
        q = (self.db.table("area_scenario_climate").select("*")
             .eq("area_id", area_id).eq("scenario_id", scenario))
        if variables:
            q = q.in_("variable_id", variables)
        return self._all(q.order("month"))

    def monthly_series(self, area_id: str, variables: list[str], date_from: str | None, date_to: str | None) -> list[dict]:
        q = (self.db.table("area_monthly_series").select("variable_id,month_date,value,anomaly")
             .eq("area_id", area_id).in_("variable_id", variables))
        if date_from:
            q = q.gte("month_date", date_from)
        if date_to:
            q = q.lte("month_date", date_to)
        return self._all(q.order("month_date"))

    def monthly_hazard(self, area_id: str, date_from: str | None, date_to: str | None) -> list[dict]:
        q = self.db.table("area_monthly_hazard").select("*").eq("area_id", area_id)
        if date_from:
            q = q.gte("month_date", date_from)
        if date_to:
            q = q.lte("month_date", date_to)
        return self._all(q.order("month_date"))

    def risk_scenario(self, area_id: str, scenario: str) -> list[dict]:
        return self._all(self.db.table("disease_risk_scenario").select("*")
                         .eq("area_id", area_id).eq("scenario_id", scenario).order("month"))

    def risk_monthly(self, area_id: str, pathogen: str | None, date_from: str | None, date_to: str | None) -> list[dict]:
        q = self.db.table("disease_risk_monthly").select("*").eq("area_id", area_id)
        if pathogen:
            q = q.eq("pathogen_id", pathogen)
        if date_from:
            q = q.gte("month_date", date_from)
        if date_to:
            q = q.lte("month_date", date_to)
        return self._all(q.order("month_date"))

    def suitability(self, area_id: str, crop: str, scenarios: list[str] | None = None) -> list[dict]:
        q = self.db.table("crop_suitability").select("*").eq("area_id", area_id).eq("crop_id", crop)
        if scenarios:
            q = q.in_("scenario_id", scenarios)
        return q.execute().data

    # ── pérdidas ──────────────────────────────────────
    _LOSS_COLS = ("area_id,name,kind,region,province,area_ha,crop_id,scenario_id,loss_pct,loss_pct_low,"
                  "loss_pct_high,exposed_ha,loss_t,loss_usd,risk_class,top_factors,model_name")
    # columnas de la migración 0010 (modelo de ML); si aún no está aplicada, se leen sin ellas
    _LOSS_ML_COLS = ",evidence,extrapolated,prob_loss_gt20,inherited_from"
    _has_ml_cols: bool | None = None

    def losses(self, crop: str, scenario: str | None = None, kind: str | None = None,
               province: str | None = None, area_id: str | None = None, with_geom: bool = False) -> list[dict]:
        if self._has_ml_cols is None:
            try:
                self.db.table("v_loss_map").select("evidence").limit(1).execute()
                SupabaseSource._has_ml_cols = True
            except Exception:  # noqa: BLE001 — falta la migración 0010
                log.warning("v_loss_map sin columnas del modelo (aplicar supabase/migrations/0010_modelo_ml.sql)")
                SupabaseSource._has_ml_cols = False
        cols = self._LOSS_COLS + (self._LOSS_ML_COLS if self._has_ml_cols else "") + (",geom" if with_geom else "")
        q = self.db.table("v_loss_map").select(cols).eq("crop_id", crop)
        if scenario:
            q = q.eq("scenario_id", scenario)
        if kind:
            q = q.eq("kind", kind)
        if province:
            q = q.eq("province", province)
        if area_id:
            q = q.eq("area_id", area_id)
        rows = self._all(q)
        if with_geom:
            for r in rows:
                r["geom"] = to_geojson(r.get("geom"))
        return rows

    def loss_full(self, model_version_id: str, area_id: str, crop: str, scenario: str) -> dict | None:
        rows = (self.db.table("loss_predictions").select("*").eq("model_version_id", model_version_id)
                .eq("area_id", area_id).eq("crop_id", crop).eq("scenario_id", scenario).limit(1).execute().data)
        if not rows:
            return None
        row = rows[0]
        if row.get("inherited_from_area_id"):      # nombre de la provincia cuyo índice usa el cantón
            prov = self.area(row["inherited_from_area_id"])
            row["inherited_from"] = prov["name"] if prov else None
        return row

    def available_scenarios(self, crop: str) -> set[str]:
        rows = self._all(self.db.table("v_loss_map").select("scenario_id").eq("crop_id", crop))
        return {r["scenario_id"] for r in rows}

    def zones(self, crop: str, future: str) -> list[dict]:
        return self._all(self.db.table("zone_classification").select("*, areas(name,parent_id)")
                         .eq("crop_id", crop).eq("future_scenario_id", future))

    # ── validación en campo ───────────────────────────
    def observations(self, area_id: str | None, pathogen: str | None, source: str | None, limit: int) -> list[dict]:
        q = self.db.table("field_observations").select("*")
        if area_id:
            q = q.eq("area_id", area_id)
        if pathogen:
            q = q.eq("pathogen_id", pathogen)
        if source:
            q = q.eq("source", source)
        return q.order("observed_on", desc=True).limit(limit).execute().data

    def insert_observation(self, token: str, row: dict[str, Any]) -> dict:
        return user_client(token).table("field_observations").insert(row).execute().data[0]
