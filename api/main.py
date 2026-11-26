import time

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from api.core.config import get_settings
from shared.core.catch_exception_middleware import CatchExceptionMiddleware
from shared.core.logging import RequestIDLoggerMiddleware, configure_logging, get_logger
from shared.core.request_context import RequestContextMiddleware
from shared.core.system import configure_fastapi
from shared.core.system import router as system_router


def create_app() -> FastAPI:

    start_time = time.perf_counter()

    settings = get_settings()  # Ensure settings are loaded before anything else

    configure_logging()

    app = FastAPI()
    configure_fastapi(app)

    # Middlewares, from innermost to outermost
    # Interesting read: https://medium.com/the-pythonworld/7-useful-middlewares-for-fastapi-that-you-should-know-about-468bd40fac0f
    app.add_middleware(CatchExceptionMiddleware)
    app.add_middleware(RequestIDLoggerMiddleware)
    app.add_middleware(RequestContextMiddleware)

    if settings.allowed_hosts:
        allowed_hosts = settings.allowed_hosts
        if "localhost" not in allowed_hosts:
            allowed_hosts.append("localhost")
        if "127.0.0.1" not in allowed_hosts:
            allowed_hosts.append("127.0.0.1")
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    if settings.redirect_https:
        # Whether to redirect HTTP to HTTPS, do not do it when behind a proxy that terminates TLS, which Cloud Run does
        app.add_middleware(HTTPSRedirectMiddleware)

    # CORS Middleware is not necessary: we do not want browsers to call these APIs
    # (we don't want the keys to leak), so this should be called from backend servers only which do not require CORS

    # Routes
    app.include_router(system_router, prefix="/v1/system")

    if settings.is_dev_environment():
        # Imported lazily: dev_routes raises at import outside development environments
        from api.core.dev_routes import router as dev_router  # noqa: PLC0415

        app.include_router(dev_router, prefix="/dev")

    end_time = time.perf_counter()
    get_logger().info("[Startup] FastAPI app started.", startup_time_ms=int((end_time - start_time) * 1000))
    return app


app = create_app()
