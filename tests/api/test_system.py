import json
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from api.main import app
from shared.core.system import ready

client = TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/v1/system/health"),
        ("get", "/v1/system/healthz"),
        ("get", "/health"),
        ("get", "/healthz"),
        ("head", "/v1/system/health"),
        ("head", "/v1/system/healthz"),
        ("head", "/health"),
        ("head", "/healthz"),
    ],
)
def test_system_health(method: str, path: str) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == HTTPStatus.OK
    if method == "get":
        assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    [
        "/v1/system/version",
        "/version",
    ],
)
def test_system_version(path: str) -> None:
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "name" in data
    assert "version" in data


class _StubDbService:
    """Stub SQLDatabaseService returning a canned test_connection() result."""

    def __init__(self, *, result: bool | Exception) -> None:
        self.result = result

    async def test_connection(self) -> bool:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_ready_healthy() -> None:
    response = await ready(db_service=_StubDbService(result=True))

    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.body) == {"status": "ok", "database": True}


async def test_ready_database_down() -> None:
    response = await ready(db_service=_StubDbService(result=ConnectionError("database is down")))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert json.loads(response.body) == {"status": "unhealthy", "database": False}


async def test_ready_without_database() -> None:
    response = await ready(db_service=None)

    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.body) == {"status": "ok", "database": None}
