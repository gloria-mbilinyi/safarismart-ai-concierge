"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

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


def test_health_endpoint_supports_root_api_prefix() -> None:
    """A root prefix should be normalized to FastAPI's empty router prefix."""

    settings = Settings(app_env="test", api_v1_prefix="/", _env_file=None)

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_only_configured_frontend_origin() -> None:
    """The local React app should be allowed without using a wildcard policy."""

    settings = Settings(
        app_env="test",
        frontend_origins="http://127.0.0.1:5173",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        allowed = client.options(
            "/api/v1/destinations",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/api/v1/destinations",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_cors_configuration_rejects_wildcards() -> None:
    """Deployment configuration must name trusted frontend origins explicitly."""

    with pytest.raises(ValidationError):
        Settings(app_env="test", frontend_origins="*", _env_file=None)
