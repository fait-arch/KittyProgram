import os

os.environ["DATA_SOURCE"] = "mock"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["MODEL_PATH"] = "models/__no_model__.joblib"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import cache  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear_all()
    yield


@pytest.fixture(scope="session")
def vinces(client):
    return next(a["id"] for a in client.get("/api/v1/areas").json() if a["name"] == "Vinces")
