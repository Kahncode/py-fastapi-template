import crud_router
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    crud_router.items.clear()
    app = FastAPI()
    app.include_router(crud_router.router)
    return TestClient(app)


def test_crud_round_trip(client: TestClient) -> None:
    created = client.post("/items", json={"name": "chair", "owner_id": 7}).json()
    assert created["status"] == "active"  # default applied
    item_id = created["id"]

    updated = client.put(f"/items/{item_id}", json={"name": "desk", "status": "archived", "owner_id": None}).json()
    assert updated["name"] == "desk"

    assert client.get(f"/items/{item_id}").json()["name"] == "desk"

    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404


def test_list_items_pagination_and_filter(client: TestClient) -> None:
    for i in range(3):
        client.post("/items", json={"name": f"item-{i}", "status": "active" if i % 2 == 0 else "archived"})

    page = client.get("/items", params={"page": 2, "page_size": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1
    assert page["page"] == 2
    assert page["page_size"] == 2

    filtered = client.get("/items", params={"status": "archived"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["name"] == "item-1"


def test_get_missing_item_returns_404(client: TestClient) -> None:
    assert client.get("/items/does-not-exist").status_code == 404
