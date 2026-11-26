from dataclasses import dataclass
from typing import Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select

from shared.services.sql_db import SQLDatabaseService

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@dataclass
class PaginationParams:
    """
    Query parameters for paginated list endpoints, to be used as a route dependency.

    Example:
        @router.get("/items")
        async def list_items(params: Annotated[PaginationParams, Depends()]) -> Page:

    """

    page: int = Query(default=1, ge=1, description="Page number, starting from 1")
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"Number of items per page (max {MAX_PAGE_SIZE})"
    )

    @property
    def offset(self) -> int:
        """Number of items to skip before this page starts."""
        return (self.page - 1) * self.page_size


class Page(BaseModel):
    """One page of results, with pagination metadata."""

    items: list[Any]
    total: int
    page: int
    page_size: int


async def paginate(db: SQLDatabaseService, statement: Select, params: PaginationParams) -> Page:
    """
    Fetch one page of rows for the given select statement, along with the total row count.

    The statement must not already contain limit/offset clauses: they are added here based on params.
    """
    total_row = await db.fetchone(select(func.count()).select_from(statement.subquery()))
    rows = await db.fetchall(statement.limit(params.page_size).offset(params.offset))
    return Page(
        items=list(rows) if rows else [],
        total=int(total_row[0]) if total_row else 0,
        page=params.page,
        page_size=params.page_size,
    )
