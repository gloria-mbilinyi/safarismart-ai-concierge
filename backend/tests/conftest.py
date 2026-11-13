"""Shared isolated database fixtures."""

from collections.abc import Iterator
from pathlib import Path
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
from app.seed.destinations import seed_destinations


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
def seeded_destinations(db_session: Session) -> list[Destination]:
    """Seed and return the curated catalog in deterministic name order."""

    seed_destinations(db_session)
    return list(
        db_session.scalars(select(Destination).order_by(Destination.name.asc())).all()
    )
