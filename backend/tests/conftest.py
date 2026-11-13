"""Shared isolated database fixtures."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.session import Database
from app.models import Base


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
