from sqlalchemy import ColumnElement


def build_filters(model: type, **params: object) -> list[ColumnElement[bool]]:
    """
    Build SQLAlchemy equality filters from the given keyword arguments, skipping None values.

    Intended for optional query parameters, e.g.:

        filters = build_filters(Item, status=status, owner_id=owner_id)
        rows = await db.fetchall(select(Item).where(*filters))

    Raises AttributeError if the model has no column matching a given (set) parameter name.
    """
    return [getattr(model, field) == value for field, value in params.items() if value is not None]
