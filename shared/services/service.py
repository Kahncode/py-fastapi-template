from collections.abc import Callable

from shared.core.config import get_settings


# Dependency for fastapi to retrieve the singleton services
def get_service[T](base_class: type[T]) -> Callable[[], T | None]:

    async def _get_service() -> T | None:
        service = get_settings().get_service(base_class)
        if service:
            async with service:
                yield service
            return
        yield None

    return _get_service
