"""Single-container Marketplace frontend serving tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def built_frontend(tmp_path: Path) -> Path:
    """Create the minimum safe Vite output shape used by the app factory."""

    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text(
        "console.log('synthetic asset')",
        encoding="utf-8",
    )
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>SafariSmart test shell</title>",
        encoding="utf-8",
    )
    return tmp_path


def test_built_frontend_serves_root_spa_routes_and_assets(tmp_path: Path) -> None:
    """One process should serve the SPA while preserving API behavior."""

    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        frontend_dist_path=str(built_frontend(tmp_path)),
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        root = client.get("/")
        spa_route = client.get("/operator")
        asset = client.get("/assets/app.js")
        health = client.get("/api/health")
        missing_api = client.get("/api/not-a-route")

    assert root.status_code == 200
    assert "SafariSmart test shell" in root.text
    assert spa_route.status_code == 200
    assert "SafariSmart test shell" in spa_route.text
    assert asset.status_code == 200
    assert "synthetic asset" in asset.text
    assert health.json() == {"status": "ok"}
    assert missing_api.status_code == 404


def test_invalid_frontend_distribution_fails_startup(tmp_path: Path) -> None:
    """A misbuilt Marketplace image must fail instead of serving partial files."""

    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        frontend_dist_path=str(tmp_path),
        _env_file=None,
    )

    try:
        create_app(settings)
    except RuntimeError as error:
        assert "built Vite application" in str(error)
    else:
        raise AssertionError("Missing frontend build should fail application creation")
