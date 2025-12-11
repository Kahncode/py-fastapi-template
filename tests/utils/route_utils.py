from inspect import signature
from typing import Annotated, get_args, get_origin

from fastapi.routing import APIRoute

from api.main import app


def get_route(path: str, method: str) -> APIRoute:
    # Find the route by path and method
    route = next(
        (r for r in app.routes if isinstance(r, APIRoute) and r.path == path and method.upper() in r.methods),
        None,
    )
    assert route is not None, f"Route {method} {path} not found"
    return route


def assert_route_has_parameter(route: APIRoute, param_name: str, param_type: type) -> None:

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
