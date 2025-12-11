from abc import ABC
from types import TracebackType
from typing import Self


# Base class for all services
class BaseService(ABC):
    type: str

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def __aenter__(self) -> Self:
        """
        Initialize context dependent variables.

        This will be called once for every request
        Optionally override in child classes
        """
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None  # noqa: A003
    ) -> None:
        """
        Cleanup context dependent variables.

        This will be called once for every request
        Optionally override in child classes
        """
        return
