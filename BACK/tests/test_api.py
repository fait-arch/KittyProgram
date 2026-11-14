"""Contrato de la API en modo mock (DATA_SOURCE=mock)."""
import pytest


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["data_source"] == "mock"
    assert r["model"]["loaded"] is False and r["ai"]["configured"] is False


@pytest.mark.parametrize("url", [
    "/api/v1/meta", "/api/v1/crops", "/api/v1/crops/cacao/requirements", "/api/v1/crops/cacao/pathogens",
    "/api/v1/crops/cacao/phenology", "/api/v1/scenarios", "/api/v1/strategies", "/api/v1/enso/current",
    "/api/v1/enso/history?from=2015-01", "/api/v1/enso/events", "/api/v1/enso/years", "/api/v1/areas",
    "/api/v1/areas?kind=province", "/api/v1/areas/geojson", "/api/v1/losses", "/api/v1/losses/summary",
    "/api/v1/losses/geojson?kind=province", "/api/v1/zones", "/api/v1/observations",
])
def test_get_ok(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("path", ["", "/climate", "/series", "/hazards", "/risk", "/risk/history",
                                  "/suitability", "/detail", "/strategies"])
def test_area_endpoints(client, vinces, path):
    assert client.get(f"/api/v1/areas/{vinces}{path}").status_code == 200


def test_province_accepts_accents_and_uuid(client):
    by_name = client.get("/api/v1/areas", params={"province": "Los Ríos"}).json()
    assert {a["name"] for a in by_name} >= {"Vinces", "Quevedo"}
    pid = by_name[0]["province"]["id"]
    assert client.get("/api/v1/areas", params={"province": pid}).json() == by_name
    assert client.get("/api/v1/areas", params={"province": "Atlantis"}).json()["code"] == "province_not_found"


def test_enso_current_banner(client):
    r = client.get("/api/v1/enso/current").json()
    assert r["phase"] == "nino" and r["oni"]["value"] == 2.46 and r["oni"]["season"] == "ASO"
    assert r["active_scenario"] == "nino" and "5.2" in r["message_es"]


def test_losses_contract(client):
    r = client.get("/api/v1/losses", params={"scenario": "nino", "province": "Los Rios"}).json()
    assert r["count"] == 5 and r["model"]["name"]
    i = r["items"][0]
    assert {"area_id", "loss_pct", "loss_pct_low", "loss_pct_high", "loss_t", "loss_usd", "risk_class"} <= i.keys()
    assert i["loss_pct_low"] <= i["loss_pct"] <= i["loss_pct_high"]
    assert [x["loss_pct"] for x in r["items"]] == sorted((x["loss_pct"] for x in r["items"]), reverse=True)


def test_summary_vs_normal(client):
    r = client.get("/api/v1/losses/summary", params={"scenario": "nino", "vs": "normal"}).json()
    assert r["totals"]["loss_t_low"] <= r["totals"]["loss_t"] <= r["totals"]["loss_t_high"]
    assert r["vs"]["delta_t"] > 0


def test_losses_geojson_has_loss_props(client):
    fc = client.get("/api/v1/losses/geojson", params={"scenario": "nino"}).json()
    assert fc["type"] == "FeatureCollection" and fc["features"]
    assert "loss_pct" in fc["features"][0]["properties"]


def test_detail_panel(client, vinces):
    d = client.get(f"/api/v1/areas/{vinces}/detail", params={"scenario": "nino"}).json()
    assert d["area"]["name"] == "Vinces" and d["loss"]["vs_normal"]["delta_pct"] > 0
    assert len(d["monthly_risk"]) == 12 and d["dominant_pathogen"] == "monilia"
    assert {c["parameter"] for c in d["requirement_check"]} >= {"temp_mean", "rain_annual"}
    assert all(c["status"] in {"ok", "warn", "bad", "sin_dato"} for c in d["requirement_check"])
    assert d["top_factors"][0]["label"] and d["disclaimer"]


def test_strategies_rank_and_priorities(client, vinces):
    r = client.get(f"/api/v1/areas/{vinces}/strategies", params={"scenario": "nino"}).json()
    ids = [i["strategy_id"] for i in r["items"]]
    assert len(ids) >= 4 and ids[-1] == "actual"          # ≥ 3 alternativas + la actual al final
    alt = [i for i in r["items"] if not i["is_current"]]
    assert [i["net_benefit_usd"] for i in alt] == sorted((i["net_benefit_usd"] for i in alt), reverse=True)
    for i in r["items"]:
        assert {"why", "evidence", "benefits", "data_gaps", "risks"} <= i.keys()
    water = client.get(f"/api/v1/areas/{vinces}/strategies",
                       params={"scenario": "nino", "priorities": "agua:5,mano_obra:5"}).json()
    assert water["items"][0]["strategy_id"] == "drenaje_sombra" and "priority_score" in water["items"][0]


def test_lookup(client, vinces):
    assert client.get("/api/v1/areas/lookup", params={"lat": -1.55, "lon": -79.75}).json()["canton"]["id"] == vinces
    assert client.get("/api/v1/areas/lookup", params={"lat": -4.5, "lon": -76.0}).status_code == 404
    assert client.get("/api/v1/areas/lookup", params={"lat": 40.0, "lon": -3.7}).status_code == 400


def test_errors(client, vinces):
    assert client.get("/api/v1/areas/nope").json()["code"] == "invalid_area_id"
    assert client.get("/api/v1/areas/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/losses", params={"scenario": "x"}).json()["code"] == "invalid_scenario"
    assert client.get(f"/api/v1/areas/{vinces}/strategies", params={"priorities": "x:9"}).status_code == 400


def test_compare_and_zones(client, vinces):
    r = client.get("/api/v1/compare", params={"area_id": vinces, "scenarios": "normal,nino,ssp585_2050"}).json()
    assert [i["scenario"] for i in r["items"]] == ["normal", "nino", "ssp585_2050"]
    z = client.get("/api/v1/zones", params={"future": "ssp585_2050"}).json()
    assert {i["zone_class"] for i in z["items"]} <= {"segura", "manejo", "transicion", "critica"}


def test_predict_synthetic_without_model(client, vinces):
    base = {"area_id": vinces, "base_scenario": "normal"}
    r0 = client.post("/api/v1/predict", json=base).json()
    r1 = client.post("/api/v1/predict", json={**base, "adjust": {"rain_delta_pct": 60, "nino12_anom": 3}}).json()
    assert r1["synthetic"] is True and r1["loss_pct"] > r0["loss_pct"]
    bad = client.post("/api/v1/predict", json={**base, "adjust": {"temp_delta_c": 9}})
    assert bad.json()["code"] == "adjust_out_of_limits"


def test_insights_without_key_is_503(client, vinces):
    r = client.get(f"/api/v1/areas/{vinces}/insights")
    assert r.status_code == 503 and r.json()["code"] == "ai_not_configured"


def test_admin_requires_key(client):
    assert client.post("/api/v1/admin/cache/clear").status_code == 403
    assert client.post("/api/v1/admin/cache/clear", headers={"X-Admin-Key": "test-admin-key"}).status_code == 200


def test_observation_requires_login(client):
    body = {"observed_on": "2026-11-10", "lat": -1.55, "lon": -79.75}
    assert client.post("/api/v1/observations", json=body).status_code == 401
