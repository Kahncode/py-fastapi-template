from datetime import UTC, datetime


def utcnow() -> datetime:
    """Get the current UTC time without timezone info and without triggering deprecation warnings."""
    return datetime.now(UTC).replace(tzinfo=None)


def datetime_notz(*args: tuple, **kwargs: object) -> datetime:
    """Construct a timezone-naive UTC datetime from the given positional arguments without triggering deprecation warnings."""
    return datetime(*args, **kwargs).astimezone(UTC).replace(tzinfo=None)
