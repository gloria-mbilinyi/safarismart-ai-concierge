"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    """The default health endpoint should report a healthy API."""

    settings = Settings(app_env="test", _env_file=None)

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_uses_configured_api_prefix() -> None:
    """The app factory should apply an environment-specific API prefix."""

    settings = Settings(app_env="test", api_v1_prefix="/service/", _env_file=None)

    with TestClient(create_app(settings)) as client:
        response = client.get("/service/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
