"""
Auditoría de la base de Supabase que usa el backend (solo lectura).

Uso, desde la carpeta BACK con el venv activo:
    python tools/auditar_supabase.py

Usa la misma conexión que el backend (BACK/.env: SUPABASE_URL + key). No imprime claves.
Muestra:
  1. Filas de cada tabla/vista que lee el backend (y si está vacía).
  2. Cobertura de lo que el front necesita: escenarios con pérdida, aptitud por escenario,
     zonas 2050, clima/riesgo por escenario, cantones sin datos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.supabase import anon_client, read_key  # noqa: E402

FRONT_SCENARIOS = ["normal", "nino", "actual", "ssp245_2050", "ssp585_2050"]

# tabla/vista -> endpoints que la leen
USED = {
    "areas": "/areas, /areas/geojson, /areas/lookup, todo el detalle",
    "area_static_features": "/areas/{id}/detail (altitud, suelo)",
    "scenarios": "/scenarios",
    "crops": "/crops",
    "crop_requirements": "/crops/{crop}/requirements, chequeo de requisitos",
    "pathogens": "/crops/{crop}/pathogens",
    "disease_thresholds": "/crops/{crop}/pathogens",
    "crop_phenology": "/crops/{crop}/phenology",
    "adaptation_strategies": "/strategies, /areas/{id}/strategies",
    "strategy_effects": "/areas/{id}/strategies",
    "data_sources": "/meta",
    "variables": "/meta",
    "model_versions": "/meta, /losses (modelo activo)",
    "crop_prices": "/areas/{id}/strategies (USD)",
    "crop_exposure": "/losses (hectáreas), /areas",
    "enso_index": "/enso/current, /enso/history",
    "enso_events": "/enso/current, /enso/events",
    "v_enso_year_class": "/enso/years",
    "area_scenario_climate": "/areas/{id}/climate, /detail, /compare",
    "area_monthly_series": "/areas/{id}/series",
    "area_monthly_hazard": "/areas/{id}/hazards",
    "disease_risk_scenario": "/areas/{id}/risk, /detail (riesgo mensual)",
    "disease_risk_monthly": "/areas/{id}/risk/history",
    "crop_suitability": "/areas/{id}/suitability, /detail, /compare",
    "loss_predictions": "/areas/{id}/detail (factores)",
    "v_loss_map": "/losses, /losses/summary, /losses/geojson, /compare",
    "zone_classification": "/zones",
    "field_observations": "/observations",
}
NOT_USED = ["crop_production_stats", "training_samples", "strategy_evaluations", "strategy_reviews",
            "field_profiles", "etl_runs", "v_training_area_year", "v_area_coverage", "v_variable_coverage",
            "v_production_provenance"]


def count(db, table, **eq):
    q = db.table(table).select("*", count="exact", head=True)
    for k, v in eq.items():
        q = q.eq(k, v)
    try:
        return q.execute().count or 0
    except Exception as e:  # tabla inexistente, permisos (RLS), red
        return f"ERROR: {str(e)[:90]}"


def main():
    _, kind = read_key()
    print(f"Conexión: key {kind}")
    db = anon_client()

    print("\n1) Tablas y vistas que lee el backend")
    empty = []
    for t, why in USED.items():
        n = count(db, t)
        flag = "  <-- VACÍA" if n == 0 else ("  <-- " + n if isinstance(n, str) else "")
        if n == 0:
            empty.append(t)
        print(f"   {t:24} {str(n):>8}   {why}{flag}")
    print("\n   No las lee el backend (solo ETL / entrenamiento):")
    for t in NOT_USED:
        print(f"   {t:24} {str(count(db, t)):>8}")

    n_cant = count(db, "areas", kind="canton")
    print(f"\n2) Cobertura para el front  (cantones en areas: {n_cant})")
    print(f"   {'escenario':14} {'pérdida':>8} {'aptitud':>8} {'clima':>8} {'riesgo':>8}")
    for s in FRONT_SCENARIOS:
        print(f"   {s:14} {str(count(db, 'v_loss_map', scenario_id=s, kind='canton')):>8}"
              f" {str(count(db, 'crop_suitability', scenario_id=s)):>8}"
              f" {str(count(db, 'area_scenario_climate', scenario_id=s)):>8}"
              f" {str(count(db, 'disease_risk_scenario', scenario_id=s)):>8}")
    print("   (clima y riesgo son filas mes × variable/patógeno, no cantones)")
    for f in ["ssp245_2050", "ssp585_2050"]:
        print(f"   zonas {f}: {count(db, 'zone_classification', future_scenario_id=f)}")

    act = db.table("model_versions").select("name,algorithm,is_active,metrics").eq("is_active", True).execute().data
    print(f"\n   Modelo activo: {act[0]['name'] if act else 'NINGUNO'}"
          f"{' (' + act[0]['algorithm'] + ')' if act else ''}")
    print("\nVacías:", ", ".join(empty) or "ninguna")


if __name__ == "__main__":
    main()
