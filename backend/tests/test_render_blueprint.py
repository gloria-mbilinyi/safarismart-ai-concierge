"""Regression checks for the public Render Free deployment contract."""

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_uses_supported_free_tier_settings() -> None:
    """Keep the Blueprint deployable without optional provider credentials."""

    blueprint = yaml.safe_load(
        (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
    )
    assert set(blueprint) == {"services"}
    assert len(blueprint["services"]) == 1

    service = blueprint["services"][0]
    assert service["type"] == "web"
    assert service["name"] == "safarismart-ai-concierge"
    assert service["runtime"] == "docker"
    assert service["plan"] == "free"
    assert service["region"] == "frankfurt"
    assert service["branch"] == "main"
    assert service["autoDeployTrigger"] == "checksPass"
    assert service["dockerContext"] == "."
    assert service["dockerfilePath"] == "./marketplace/Dockerfile"
    assert service["healthCheckPath"] == "/api/health"
    assert "maxShutdownDelaySeconds" not in service

    environment = {item["key"]: item for item in service["envVars"]}
    assert environment["APP_ENV"]["value"] == "production"
    assert environment["APP_DEBUG"]["value"] == "false"
    assert environment["AI_PROVIDER"]["value"] == "fallback"
    assert environment["EMAIL_ENABLED"]["value"] == "false"
    assert environment["SMS_ENABLED"]["value"] == "false"
    assert environment["AUTH_SECRET_KEY"]["generateValue"] is True
    assert environment["DATABASE_URL"]["sync"] is False
    assert "RESEND_API_KEY" not in environment
    assert "RESEND_FROM_EMAIL" not in environment

    prompted_secrets = {
        item["key"] for item in service["envVars"] if item.get("sync") is False
    }
    assert prompted_secrets == {"DATABASE_URL"}
