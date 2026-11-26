from datetime import timedelta

import jwt_oauth2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt_oauth2 import create_access_token


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(jwt_oauth2.router)
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def test_login_returns_token_that_authenticates(client: TestClient) -> None:
    token = _login(client, "alice", "wonderland")["access_token"]

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"username": "alice", "role": "admin"}


def test_login_rejects_wrong_password(client: TestClient) -> None:
    assert client.post("/login", data={"username": "alice", "password": "nope"}).status_code == 401


def test_me_rejects_missing_tampered_or_unknown_tokens(client: TestClient) -> None:
    assert client.get("/me").status_code == 401  # no token
    assert client.get("/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401  # tampered
    ghost_token = create_access_token("ghost")
    assert client.get("/me", headers={"Authorization": f"Bearer {ghost_token}"}).status_code == 401  # unknown user


def test_expired_token_is_rejected(client: TestClient) -> None:
    expired = create_access_token("alice", expires_delta=timedelta(minutes=-1))

    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
