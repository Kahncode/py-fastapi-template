import asyncio
import time
from types import SimpleNamespace

import pytest
import rate_limiting
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from rate_limiting import RateLimiter


async def _dummy_endpoint() -> dict[str, str]:
    return {"status": "ok"}


def test_rate_limiter_blocks_after_max_requests() -> None:
    app = FastAPI()
    app.add_api_route(
        "/limited", _dummy_endpoint, dependencies=[Depends(RateLimiter(max_requests=3, window_seconds=60.0))]
    )
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/limited").status_code == 200

    response = client.get("/limited")
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"
    assert "Retry-After" in response.headers


def test_rate_limiter_isolates_clients() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)

    class FakeRequest:
        def __init__(self, host: str) -> None:
            self.client = SimpleNamespace(host=host)

    async def call(client_host: str) -> None:
        await limiter(FakeRequest(client_host))

    asyncio.run(call("1.1.1.1"))
    asyncio.run(call("2.2.2.2"))  # allowed: separate window per client


def test_rate_limiter_window_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])

    limiter = RateLimiter(max_requests=1, window_seconds=10.0)

    class FakeRequest:
        client = SimpleNamespace(host="1.2.3.4")

    async def call() -> None:
        await limiter(FakeRequest())

    asyncio.run(call())
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(call())
    assert exc_info.value.status_code == 429

    now[0] += 11.0  # window has fully passed
    asyncio.run(call())  # allowed again


def test_module_demo_route_is_limited() -> None:
    app = FastAPI()
    app.include_router(rate_limiting.router)
    client = TestClient(app)

    for _ in range(5):
        assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429
