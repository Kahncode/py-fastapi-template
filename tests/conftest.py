from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from pytest_postgresql import factories
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.core.auth import authorize_api_key
from shared.core.config import get_settings
from shared.services.file_storage import FileStorageService
from shared.services.local_file_storage import LocalFileStorageService
from shared.services.sql_db import Base, SQLDatabaseService

TEST_API_KEY = "default_test_api_key"


def get_fastapi_app() -> FastAPI:
    from api.main import app  # noqa: PLC0415

    return app


def seed_db(**kwags: object) -> None:
    """Seed the database with initial data (sync, SQLAlchemy + psycopg)."""
    url = f"postgresql+psycopg://{kwags['user']}:{kwags['password'] or ''}@{kwags['host']}:{kwags['port']}/{kwags['dbname']}"
    engine = create_engine(url)
    session = sessionmaker(bind=engine)()

    # Collect all schema names from your models
    schemas = {table.schema for table in Base.metadata.tables.values() if table.schema}
    with engine.connect() as conn:
        for schema in schemas:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        conn.commit()

        # Create all tables
        Base.metadata.create_all(bind=engine)

    # Seed the database with initial data most routes will need, for example an api_key
    # api_key = ApiKey(TEST_API_KEY...)
    # session.add(api_key) # noqa: ERA001
    # session.commit() # noqa: ERA001
    session.close()


seeded_postgresql_proc = factories.postgresql_proc(
    port=5454, user="postgres", password="", dbname="tests", host="127.0.0.1", load=[seed_db]
)
seeded_postgresql = factories.postgresql("seeded_postgresql_proc")


class SeededDB:
    db: SQLDatabaseService
    api_key: str


@pytest.fixture
async def seeded_db(seeded_postgresql) -> SeededDB:  # noqa: ANN001
    postgresql = seeded_postgresql

    async with get_settings().get_service(SQLDatabaseService) as db:
        # Patch URL for our regular service to connect to
        db.url = f"postgresql+asyncpg://{postgresql.info.user}:{postgresql.info.password or ""}@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"

        result = SeededDB()
        result.db = db
        result.api_key = TEST_API_KEY

        yield result

        # Fully disconnecting to avoid "Task got Future attached to a different loop" errors
        await db.disconnect()


# Necessary class to mock route dependencies without affecting the route's expected parameters
class NoArgMock(Mock):
    def __call__(self) -> Mock:
        return super().__call__()


@pytest.fixture
def mock_authorize_api_key(seeded_db: SeededDB) -> NoArgMock:
    mock = NoArgMock(return_value=seeded_db.api_key)
    get_fastapi_app().dependency_overrides[authorize_api_key] = mock

    yield mock

    assert mock.called, "Expected authorize_api_key to be called at least once"
    get_fastapi_app().dependency_overrides = {}


@pytest.fixture
def temp_file_storage(tmp_path: Path) -> FileStorageService:
    """
    Provide a FileStorageService instance that uses a temporary directory for storage.

    The temporary directory and its contents are deleted after the test.
    """
    service = LocalFileStorageService()
    service.root_path = tmp_path

    return service


@pytest.fixture
def mock_background_tasks() -> Mock:
    """
    Provide a mock BackgroundTasks instance which calls or awaits the background task immediately.
    """
    """
    Provide a mock BackgroundTasks instance which stores background tasks and allows running them later.
    """
    mock = Mock()
    mock.tasks = []

    def add_task(func: Callable, *args: tuple, **kwargs: object) -> None:
        mock.tasks.append((func, args, kwargs))

    mock.add_task = Mock(side_effect=add_task)

    async def run() -> None:
        for func, args, kwargs in mock.tasks:
            result = func(*args, **kwargs)
            if callable(getattr(result, "__await__", None)):
                await result
        mock.tasks.clear()

    mock.run = Mock(side_effect=run)

    yield mock

    assert mock.add_task.called, "Expected add_task to be called at least once"
    assert mock.run.called, "Expected run to be called at least once"


@pytest.fixture
def get_test_resources() -> Path:
    return Path(__file__).parent / "resources"


def get_test_resources_path() -> Path:
    return Path(__file__).parent / "resources"
