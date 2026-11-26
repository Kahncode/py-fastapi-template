from abc import ABC
from types import TracebackType
from typing import Self


# Base class for all services; subclass-declared abstract methods rely on this ABC base in the MRO
class BaseService(ABC):  # noqa: B024
    async def __aenter__(self) -> Self:
        """
        Initialize context dependent variables.

        This will be called once for every request
        Optionally override in child classes
        """
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """
        Cleanup context dependent variables.

        This will be called once for every request
        Optionally override in child classes
        """
        return
