from collections.abc import Callable, Iterator
from inspect import signature
from typing import Annotated, Protocol, get_args, get_origin

from fastapi.routing import APIRoute

from api.main import app


class RouteLike(Protocol):
    path: str
    methods: set[str] | None
    endpoint: Callable[..., object] | None


def iter_api_routes() -> Iterator[RouteLike]:
    """
    Yield every effective API route (path, methods, endpoint), including those from included routers.

    FastAPI >= 0.16x wraps included routers lazily, so `app.routes` no longer contains flat `APIRoute` objects.
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()


def get_route(path: str, method: str) -> RouteLike:
    # Find the route by path and method
    route = next(
        (r for r in iter_api_routes() if r.path == path and method.upper() in r.methods),
        None,
    )
    assert route is not None, f"Route {method} {path} not found"
    return route


def assert_route_has_parameter(route: RouteLike, param_name: str, param_type: type) -> None:

    # Check route's endpoint signature for parameter name and type
    sig = signature(route.endpoint)
    found = False
    for name, param in sig.parameters.items():
        anno = param.annotation
        # If Annotated, extract the first argument (the real type)
        if get_origin(anno) is Annotated:
            anno = get_args(anno)[0]
        if name == param_name and anno is param_type:
            found = True
            break
    assert found, f"Route {route} does not have parameter '{param_name}' of type {param_type}"


def assert_route_has_parameters(path: str, method: str, params: dict[str, type]) -> None:
    route = get_route(path, method)
    for param_name, param_type in params.items():
        assert_route_has_parameter(route, param_name, param_type)
