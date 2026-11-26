import background_tasks
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    background_tasks.sent_emails.clear()
    app = FastAPI()
    app.include_router(background_tasks.router)
    return TestClient(app)


def test_signup_runs_background_task(client: TestClient) -> None:
    response = client.post("/signup", json={"email": "user@example.com"})

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}
    assert background_tasks.sent_emails == {"user@example.com"}


def test_signup_survives_failing_background_task(client: TestClient) -> None:
    response = client.post("/signup", json={"email": "bounce@example.com"})

    # The failure is logged by safe_task instead of being raised
    assert response.status_code == 200
    assert background_tasks.sent_emails == set()


async def test_safe_task_supports_sync_and_async_tasks() -> None:
    calls: list[str] = []

    def sync_task(name: str) -> None:
        calls.append(f"sync:{name}")

    async def async_task(name: str) -> None:
        calls.append(f"async:{name}")

    await background_tasks.safe_task(sync_task, "a")
    await background_tasks.safe_task(async_task, "b")

    assert calls == ["sync:a", "async:b"]
