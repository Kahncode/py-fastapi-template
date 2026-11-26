from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.utils.filters import build_filters


class _Base(DeclarativeBase):
    pass


class _Item(_Base):
    __tablename__ = "test_filter_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


def test_build_filters_skips_unset_params() -> None:
    filters = build_filters(_Item, status="active", owner_id=None)

    assert len(filters) == 1
    assert filters[0].compare(_Item.status == "active")


def test_build_filters_keeps_falsy_values() -> None:
    # 0 and False must not be treated as "unset": only None is skipped
    filters = build_filters(_Item, owner_id=0, status=False)

    assert len(filters) == 2  # noqa: PLR2004 - one filter per falsy-but-set value
    assert filters[0].compare(_Item.owner_id == 0)
    assert filters[1].compare(_Item.status == False)  # noqa: E712 - SQLAlchemy expression, not a bool comparison


def test_build_filters_ignores_unknown_param_when_unset() -> None:
    # A None param is skipped before looking up the column, so unknown names are tolerated when unset
    assert build_filters(_Item, category=None) == []
