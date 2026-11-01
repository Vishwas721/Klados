from fastapi.testclient import TestClient
import pytest

from app import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", "s3cret")
    return TestClient(main.app)


def test_api_requires_key_when_configured(client):
    assert client.get("/api/targets").status_code == 401
    assert client.get("/api/targets", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/targets", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_health_stays_open(client):
    assert client.get("/health").status_code == 200


def test_cors_preflight_not_blocked(client):
    res = client.options(
        "/api/targets",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "x-api-key"},
    )
    assert res.status_code == 200


def test_open_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", None)
    assert TestClient(main.app).get("/api/targets").status_code == 200
