from collections.abc import Callable

from fastapi import HTTPException, status

from shared.core.config import get_settings


# Dependency for fastapi to retrieve the singleton services
def get_service[T](base_class: type[T]) -> Callable[[], T]:

    async def _get_service() -> T:
        service = get_settings().get_service(base_class)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No {base_class.__name__} configured",
            )
        async with service:
            yield service

    return _get_service
