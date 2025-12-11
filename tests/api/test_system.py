from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from api.main import app

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
