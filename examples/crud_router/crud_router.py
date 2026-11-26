"""
CRUD router example backed by an in-memory store.

Demonstrates typed request/response models, pagination and filtering, using the helpers from
`shared.utils`. Replace the module-level store with a database service in a real application.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shared.utils.pagination import Page, PaginationParams

router = APIRouter(tags=["items"])


class ItemIn(BaseModel):
    """Payload for creating or updating an item."""

    name: str
    status: str = "active"
    owner_id: int | None = None


class Item(ItemIn):
    """Item as stored and returned by the API."""

    id: str


# In-memory store: swap for a database in a real application
items: dict[str, Item] = {}


def _get_item_or_404(item_id: str) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Item not found")
    return item


@router.get("/items")
async def list_items(params: Annotated[PaginationParams, Depends()], status: str | None = None) -> Page:
    """List items, optionally filtered by exact status match."""
    matches = [item for item in items.values() if status is None or item.status == status]
    start = params.offset
    return Page(
        items=matches[start : start + params.page_size],
        total=len(matches),
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/items", status_code=HTTPStatus.CREATED)
async def create_item(item_in: ItemIn) -> Item:
    """Create an item with a generated id."""
    item = Item(id=uuid4().hex, **item_in.model_dump())
    items[item.id] = item
    return item


@router.get("/items/{item_id}")
async def get_item(item_id: str) -> Item:
    """Fetch one item by id."""
    return _get_item_or_404(item_id)


@router.put("/items/{item_id}")
async def update_item(item_id: str, item_in: ItemIn) -> Item:
    """Replace an item's fields."""
    item = _get_item_or_404(item_id)
    for field, value in item_in.model_dump().items():
        setattr(item, field, value)
    return item


@router.delete("/items/{item_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_item(item_id: str) -> None:
    """Delete an item by id."""
    _get_item_or_404(item_id)
    del items[item_id]
