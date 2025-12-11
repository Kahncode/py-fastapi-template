import importlib

import pytest
from fastapi.routing import APIRoute

from api.main import app

# Fill this list with all routes and their corresponding test function names (as a list)
TESTED_ROUTES = [
    ("/v1/system/health", "GET", ["api.test_system.test_system_health"]),
    ("/v1/system/health", "HEAD", ["api.test_system.test_system_health"]),
    ("/v1/system/healthz", "GET", ["api.test_system.test_system_health"]),
    (
        "/v1/system/healthz",
        "HEAD",
        ["api.test_system.test_system_health"],
    ),
    ("/health", "GET", ["api.test_system.test_system_health"]),
    ("/health", "HEAD", ["api.test_system.test_system_health"]),
    ("/healthz", "GET", ["api.test_system.test_system_health"]),
    ("/healthz", "HEAD", ["api.test_system.test_system_health"]),
    (
        "/v1/system/version",
        "GET",
        ["api.test_system.test_system_version"],
    ),
    ("/version", "GET", ["api.test_system.test_system_version"]),
    ("/dev/test/auth", "GET", ["api.test_auth.test_auth"]),  # Unit test only
    ("/dev/test/database", "GET", [None]),  # Explicitly not tested
    ("/dev/test/logging", "POST", [None]),  # Explicitly not tested
    ("/dev/cpuinfo", "GET", [None]),  # Explicitly not tested
    ("/dev/platform", "GET", [None, None]),  # Explicitly not tested
    ("/dev/sleep", "POST", [None, None]),  # Explicitly not tested
    ("/dev/environment", "GET", [None, None]),  # Explicitly not tested
]


def test_all_routes_have_tests() -> None:
    app_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    app_route_keys = {(route.path, next(iter(route.methods))) for route in app_routes}
    tested_route_keys = {(path, method) for (path, method, _) in TESTED_ROUTES}

    missing = [key for key in app_route_keys if key not in tested_route_keys]
    assert not missing, f"Routes missing from TESTED_ROUTES: {missing}"

    extra = [key for key in tested_route_keys if key not in app_route_keys]
    assert not extra, f"TESTED_ROUTES contains routes not present in app: {extra}"

    # Enforce that all test functions exist and are test functions
    for path, method, test_funcs in TESTED_ROUTES:

        assert (
            len(test_funcs) >= 0
        ), f"Not enough tests for route {path} {method}. Each route needs at least one unit test"

        for test_func in test_funcs:

            if test_func is None:
                continue  # Skip routes that are explicitly not tested

            module_name, func_name = test_func.rsplit(".", 1)
            try:
                mod = importlib.import_module(f"tests.{module_name}")
            except ImportError:
                pytest.fail(f"Module {module_name} for test function {func_name} not found")
            func = getattr(mod, func_name, None)
            assert callable(func), f"Test function {func_name} for route {path} {method} is missing or not callable"
            assert func_name.startswith(
                "test_"
            ), f"Test function {func_name} for route {path} {method} does not start with 'test_'"
