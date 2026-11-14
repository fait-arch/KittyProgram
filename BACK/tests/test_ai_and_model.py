"""IA con cliente falso (no gasta API) y predictor con un bundle sklearn real del contrato."""
import json
from types import SimpleNamespace

import joblib
import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import get_settings
from app.services import ai_providers, predictor

FAKE = {
    "resumen": "Vinces tiene riesgo alto de moniliasis en un año Niño.",
    "nivel_alerta": "alto",
    "hallazgos": [{"titulo": "Mucha humedad", "detalle": "Ene–mar muy húmedos.", "evidencia": "ERA5-Land: 120 días favorables"}],
    "recomendaciones": [{"accion": "Cosecha sanitaria semanal", "por_que": "Corta el ciclo de la moniliasis",
                         "cuando": "enero a abril", "prioridad": "alta", "estrategia_id": "sanitario"}],
    "meses_criticos": [1, 2, 3],
    "vacios_de_datos": ["Umbrales no validados"],
    "validar_con_experto": ["Costo de mano de obra"],
}


class FakeHTTP:
    """Simula POST https://api.deepseek.com/chat/completions."""
    def __init__(self, contents, finish="stop", status=200):
        self.contents, self.finish, self.status, self.calls = list(contents), finish, status, []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        content = self.contents.pop(0) if self.contents else ""
        body = {"model": json["model"], "choices": [{"finish_reason": self.finish, "message": {"content": content}}]}
        return SimpleNamespace(status_code=self.status, json=lambda: body, text=str(body))


@pytest.fixture
def deepseek(monkeypatch):
    def make(contents, **kw):
        fake = FakeHTTP(contents, **kw)
        monkeypatch.setattr(get_settings(), "ai_provider", "deepseek")
        monkeypatch.setattr(get_settings(), "deepseek_api_key", "test-key")
        monkeypatch.setattr(ai_providers.httpx, "post", fake)
        return fake
    return make


def test_insights_deepseek_json(client, vinces, deepseek):
    fake = deepseek([json.dumps(FAKE)])
    r = client.get(f"/api/v1/areas/{vinces}/insights", params={"scenario": "nino", "priorities": "ingreso:5"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "deepseek" and body["nivel_alerta"] == "alto"
    req = fake.calls[0]
    assert req["url"].endswith("/chat/completions") and req["headers"]["Authorization"] == "Bearer test-key"
    assert req["json"]["model"] == "deepseek-chat" and req["json"]["response_format"] == {"type": "json_object"}
    assert req["json"]["messages"][0]["role"] == "system" and "json" in req["json"]["messages"][0]["content"]
    assert "Vinces" in req["json"]["messages"][1]["content"]
    client.get(f"/api/v1/areas/{vinces}/insights", params={"scenario": "nino", "priorities": "ingreso:5"})
    assert len(fake.calls) == 1   # segunda vez sale de la caché


def test_insights_retries_bad_json(client, vinces, deepseek):
    fake = deepseek(['{"resumen": "incompleto"}', json.dumps(FAKE)])
    assert client.get(f"/api/v1/areas/{vinces}/insights").status_code == 200
    assert len(fake.calls) == 2
    deepseek(["no es json", "tampoco"])
    from app.core import cache
    cache.clear_all()
    assert client.get(f"/api/v1/areas/{vinces}/insights").json()["code"] == "ai_bad_output"


def test_deepseek_errors(client, vinces, deepseek):
    deepseek([""], status=402)
    assert client.get(f"/api/v1/areas/{vinces}/insights").json()["code"] == "ai_no_balance"
    deepseek([""], finish="length")
    assert client.post(f"/api/v1/areas/{vinces}/ask", json={"question": "¿Qué hago?"}).json()["code"] == "ai_truncated"


def test_ask_deepseek(client, vinces, deepseek):
    fake = deepseek(["Revise las mazorcas cada semana."])
    r = client.post(f"/api/v1/areas/{vinces}/ask", json={
        "question": "¿Cuándo debo podar?", "history": [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola"}]})
    assert r.status_code == 200 and "mazorcas" in r.json()["answer"]
    msgs = fake.calls[0]["json"]["messages"]
    assert msgs[-1] == {"role": "user", "content": "¿Cuándo debo podar?"} and "response_format" not in fake.calls[0]["json"]


class FakeClaude:
    def __init__(self, stop="end_turn"):
        self.calls, self.stop = [], stop

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop, model=kw["model"],
                               content=[SimpleNamespace(type="text", text=json.dumps(FAKE))])


def test_insights_anthropic(client, vinces, monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(get_settings(), "ai_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test")
    monkeypatch.setattr(ai_providers, "_anthropic_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=fake)))
    r = client.get(f"/api/v1/areas/{vinces}/insights").json()
    assert r["provider"] == "anthropic" and fake.calls[0]["model"] == "claude-opus-5-5"
    assert fake.calls[0]["output_config"]["format"]["type"] == "json_schema" and fake.calls[0]["fallbacks"] == "default"
    fake.stop = "refusal"
    from app.core import cache
    cache.clear_all()
    assert client.get(f"/api/v1/areas/{vinces}/insights").json()["code"] == "ai_refused"


@pytest.fixture
def model_bundle(tmp_path, monkeypatch):
    feats = ["fav_days_monilia", "fav_days_phytophthora", "heavy_rain_days", "nino12_anom_jan_jun", "oni_jan_jun", "suitability_now"]
    rng = np.random.default_rng(0)
    X = rng.uniform([60, 40, 0, -1, -1, 0.5], [180, 150, 40, 4, 2.5, 0.95], size=(140, len(feats)))
    y = -(0.12 * X[:, 0] + 0.05 * X[:, 1] + 0.3 * X[:, 2] + 2.0 * X[:, 3]) + 15 + rng.normal(0, 2, 140)
    q = lambda a: GradientBoostingRegressor(loss="quantile", alpha=a, max_depth=2, n_estimators=50).fit(X, y)
    bundle = {"version": "test_v1", "features": feats,
              "model": make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X, y),
              "low": q(0.1), "high": q(0.9),
              "feature_means": dict(zip(feats, X.mean(0).round(3).tolist())),
              "feature_ranges": {f: [float(X[:, i].min()), float(X[:, i].max())] for i, f in enumerate(feats)}}
    import pandas as pd
    for k in ("model", "low", "high"):   # el predictor usa DataFrame con nombres de columna
        bundle[k].fit(pd.DataFrame(X, columns=feats), y)
    path = tmp_path / "m.joblib"
    joblib.dump(bundle, path)
    monkeypatch.setattr(get_settings(), "model_path", str(path))
    predictor.load()
    yield bundle
    monkeypatch.undo()
    predictor.load()


def test_predict_with_real_bundle(client, vinces, model_bundle):
    assert client.get("/health").json()["model"]["loaded"] is True
    base = {"area_id": vinces, "base_scenario": "normal"}
    r0 = client.post("/api/v1/predict", json=base).json()
    r1 = client.post("/api/v1/predict", json={**base, "adjust": {"rain_delta_pct": 50, "nino12_anom": 3.5}}).json()
    assert r0["synthetic"] is False and r0["model"]["name"] == "test_v1"
    assert set(r0["features_base"]) >= {"fav_days_monilia", "heavy_rain_days", "nino12_anom_jan_jun"}
    assert r1["loss_pct"] > r0["loss_pct"]
    assert r1["top_factors"] and r1["top_factors"][0]["label"]
    assert r1["loss_pct_low"] is not None and r1["loss_pct_high"] is not None


def test_predict_arthur_style_bundle(client, vinces, tmp_path, monkeypatch):
    """Nombres del paquete ml/ (nino12_jan_jun, suitability, rain_total) y features como anomalías por área."""
    feats = ["rain_total", "fav_days_monilia", "heavy_rain_days", "nino12_jan_jun", "suitability"]
    rng = np.random.default_rng(1)
    X = rng.normal(0, [400, 30, 5, 1.5, 0.05], size=(120, len(feats)))   # anomalías (media 0)
    y = -(0.01 * X[:, 0] + 0.1 * X[:, 1] + 0.5 * X[:, 2] + 2 * X[:, 3]) + rng.normal(0, 1, 120)
    import pandas as pd
    m = make_pipeline(StandardScaler(), Ridge()).fit(pd.DataFrame(X, columns=feats), y)
    means = {"rain_total": 1500.0, "fav_days_monilia": 100.0, "heavy_rain_days": 8.0, "nino12_jan_jun": 0.3, "suitability": 0.8}
    path = tmp_path / "arthur.joblib"
    joblib.dump({"version": "arthur_v1", "features": feats, "model": m, "area_means": {"Vinces": means}}, path)
    monkeypatch.setattr(get_settings(), "model_path", str(path))
    predictor.load()
    try:
        base = {"area_id": vinces, "base_scenario": "normal"}
        r0 = client.post("/api/v1/predict", json=base).json()
        r1 = client.post("/api/v1/predict", json={**base, "adjust": {"rain_delta_pct": 50, "nino12_anom": 3.5}}).json()
        assert r0["model"]["name"] == "arthur_v1"
        assert {"rain_total", "nino12_jan_jun", "suitability"} <= set(r0["features_base"])
        assert r1["features_used"]["nino12_jan_jun"] == 3.5 and r1["loss_pct"] > r0["loss_pct"]
    finally:
        monkeypatch.undo()
        predictor.load()
