"""API tests. Run in CI before every deploy. Hermetic: no real GCP, no dependence on shell/.env."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from shoppilot.api import main
from shoppilot.config import get_settings


@pytest.fixture
def client(monkeypatch):
    # FORCE test values. Env vars beat .env, and setenv overrides whatever your shell exported.
    monkeypatch.setenv("PROJECT_ID", "test-project")
    monkeypatch.setenv("API_KEY", "test-key")
    get_settings.cache_clear()  # drop any Settings cached by a previous test

    # Fake GCS client, auto-restored after each test (unlike direct assignment)
    monkeypatch.setattr(main.storage, "Client", MagicMock())

    with TestClient(main.app) as c:
        yield c

    get_settings.cache_clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_policies_requires_api_key(client):
    assert client.get("/policies").status_code == 401
    assert client.get("/policies", headers={"X-API-Key": "wrong"}).status_code == 401


def test_list_policies(client):
    blob = MagicMock()
    blob.name = "policies/refund-policy.md"
    client.app.state.gcs.list_blobs.return_value = [blob]

    r = client.get("/policies", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    assert r.json() == {"policies": ["refund-policy.md"]}
