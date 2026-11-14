"""Shared isolated database fixtures."""

from collections.abc import Iterator
from pathlib import Path
import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models import Base
from app.models.destination import Destination
from app.models.operator_user import OperatorUser
from app.seed.destinations import seed_destinations
from app.services.operator_bootstrap import bootstrap_demo_operator
from app.security.tokens import create_operator_access_token


@pytest.fixture
def database() -> Iterator[Database]:
    """Create a new temporary SQLite database for each test."""

    database_path = Path(__file__).parent / f".test-{uuid4().hex}.db"
    test_database = Database(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(test_database.engine)

    try:
        yield test_database
    finally:
        Base.metadata.drop_all(test_database.engine)
        test_database.dispose()
        database_path.unlink(missing_ok=True)


@pytest.fixture
def db_session(database: Database) -> Iterator[Session]:
    """Yield a transaction-capable session against an isolated database."""

    with database.session_factory() as session:
        yield session


@pytest.fixture
def client(database: Database) -> Iterator[TestClient]:
    """Yield an API client connected to the isolated test database."""

    settings = Settings(
        app_env="test",
        database_url=str(database.engine.url),
        _env_file=None,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def auth_settings(database: Database) -> Settings:
    """Return test settings with an unpredictable per-test signing key."""

    return Settings(
        app_env="test",
        database_url=str(database.engine.url),
        auth_secret_key=secrets.token_urlsafe(48),
        _env_file=None,
    )


@pytest.fixture
def auth_client(auth_settings: Settings) -> Iterator[TestClient]:
    """Yield an API client with operator authentication configured."""

    with TestClient(create_app(auth_settings)) as test_client:
        yield test_client


@pytest.fixture
def demo_password() -> str:
    """Return an unpredictable password used only for one isolated test."""

    return secrets.token_urlsafe(24)


@pytest.fixture
def demo_operator_user(db_session: Session, demo_password: str) -> OperatorUser:
    """Create one synthetic active operator identity for authentication tests."""

    _, user = bootstrap_demo_operator(
        db_session,
        operator_name="SafariSmart Synthetic Safaris",
        operator_slug="safarismart-synthetic-safaris",
        user_email="demo.operator@example.test",
        user_full_name="Demo Operator",
        password=demo_password,
    )
    return user


@pytest.fixture
def operator_token(
    auth_settings: Settings,
    demo_operator_user: OperatorUser,
) -> str:
    """Issue a token for the synthetic operator identity."""

    return create_operator_access_token(demo_operator_user, auth_settings)


@pytest.fixture
def operator_headers(operator_token: str) -> dict[str, str]:
    """Return the bearer header for the synthetic operator identity."""

    return {"Authorization": f"Bearer {operator_token}"}


@pytest.fixture
def seeded_destinations(db_session: Session) -> list[Destination]:
    """Seed and return the curated catalog in deterministic name order."""

    seed_destinations(db_session)
    return list(
        db_session.scalars(select(Destination).order_by(Destination.name.asc())).all()
    )
