from sqlalchemy import column, select

from shared.utils.pagination import Page, PaginationParams, paginate

# A standalone column expression, enough to exercise limit/offset/subquery handling
_statement = select(column("id"))


class FakeDbService:
    """Minimal stand-in for SQLDatabaseService returning canned results and capturing statements."""

    def __init__(self, total: int, rows: list[str]) -> None:
        self.total = total
        self.rows = rows
        self.captured_statements: list[object] = []

    async def fetchone(self, statement: object, _params: dict | None = None) -> tuple[int]:
        self.captured_statements.append(statement)
        return (self.total,)

    async def fetchall(self, statement: object, _params: dict | None = None) -> list[str]:
        self.captured_statements.append(statement)
        return self.rows


# Page 3 with page size 10 skips the first two full pages
_OFFSET_PAGE_3_SIZE_10 = 20


def test_pagination_params_offset() -> None:
    assert PaginationParams(page=1, page_size=50).offset == 0
    assert PaginationParams(page=3, page_size=10).offset == _OFFSET_PAGE_3_SIZE_10


async def test_paginate_returns_rows_and_metadata() -> None:
    db = FakeDbService(total=42, rows=["row-a", "row-b"])

    page = await paginate(db, _statement, PaginationParams(page=2, page_size=25))

    assert page == Page(items=["row-a", "row-b"], total=42, page=2, page_size=25)
    count_statement, rows_statement = db.captured_statements
    assert "count" in str(count_statement).lower()
    rendered_rows = str(rows_statement.compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 25" in rendered_rows
    assert "OFFSET 25" in rendered_rows


async def test_paginate_empty_result() -> None:
    db = FakeDbService(total=0, rows=[])

    page = await paginate(db, _statement, PaginationParams(page=1, page_size=50))

    assert page.total == 0
    assert page.items == []
