"""Alembic migration and seed integration tests."""

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select

from app.db.session import Database
from app.models.destination import Destination
from app.seed.destinations import seed_destinations


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_TABLES = {
    "operators",
    "destinations",
    "booking_requests",
    "booking_status_history",
    "operator_users",
    "booking_quotes",
    "booking_notifications",
}


def test_migration_upgrade_seed_and_downgrade() -> None:
    """The migration should create a seedable schema and cleanly downgrade."""

    database_path = Path(__file__).parent / f".migration-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.attributes["database_url"] = database_url

    try:
        command.upgrade(alembic_config, "head")
        database = Database(database_url)
        try:
            assert DOMAIN_TABLES.issubset(set(inspect(database.engine).get_table_names()))
            with database.session_factory() as session:
                assert seed_destinations(session) == 5
                assert seed_destinations(session) == 0
                assert (
                    session.scalar(select(func.count()).select_from(Destination)) == 5
                )
        finally:
            database.dispose()

        command.check(alembic_config)
        command.downgrade(alembic_config, "base")

        downgraded_database = Database(database_url)
        try:
            remaining_tables = set(
                inspect(downgraded_database.engine).get_table_names()
            )
            assert DOMAIN_TABLES.isdisjoint(remaining_tables)
        finally:
            downgraded_database.dispose()
    finally:
        database_path.unlink(missing_ok=True)
