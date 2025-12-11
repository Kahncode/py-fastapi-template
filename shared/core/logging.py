import json
import logging
import sys
import time
import uuid

import structlog
from fastapi import Request
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from shared.core.config import AppEnvironment, get_settings
from shared.core.request_context import request_context

_logging_configured: bool = False


def configure_logging() -> None:
    global _logging_configured  # noqa: PLW0603
    if _logging_configured:
        return

    _logging_configured = True

    # Only use json logs for cloud deployments
    json_logs: bool = get_settings().app_environment != AppEnvironment.LOCAL

    if json_logs:

        # Copied from https://www.structlog.org/en/stable/standard-library.html
        # Note: only OUR logs will be in JSON format, other libraries may still log in plain text
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=get_settings().log_level.upper(),
        )

        processors = [
            # If log level is too low, abort pipeline and throw away log entry.
            structlog.stdlib.filter_by_level,
            # Add the name of the logger to event dict.
            structlog.stdlib.add_logger_name,
            # Add log level to event dict.
            structlog.stdlib.add_log_level,
            # Perform %-style formatting.
            structlog.stdlib.PositionalArgumentsFormatter(),
            # Add a timestamp in ISO 8601 format.
            structlog.processors.TimeStamper(fmt="iso"),
            # If the "stack_info" key in the event dict is true, remove it and
            # render the current stack trace in the "stack" key.
            structlog.processors.StackInfoRenderer(),
            # If the "exc_info" key in the event dict is either true or a
            # sys.exc_info() tuple, remove "exc_info" and render the exception
            # with traceback into the "exception" key.
            structlog.processors.format_exc_info,
            # If some value is in bytes, decode it to a Unicode str.
            structlog.processors.UnicodeDecoder(),
            # Add callsite parameters.
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
        ]

        # Add additional log processors at the end of the stack
        processors.extend(get_settings().log_processors or [])

        # Render the final event dict as JSON.
        processors.append(structlog.processors.JSONRenderer())

        structlog.configure(
            processors,
            # `wrapper_class` is the bound logger that you get back from
            # get_logger(). This one imitates the API of `logging.Logger`.
            wrapper_class=structlog.stdlib.BoundLogger,
            # `logger_factory` is used to create wrapped loggers that are used for
            # OUTPUT. This one returns a `logging.Logger`. The final value (a JSON
            # string) from the final processor (`JSONRenderer`) will be passed to
            # the method of the same name as that you've called on the bound logger.
            logger_factory=structlog.stdlib.LoggerFactory(),
            # Effectively freeze configuration after creating the first bound
            # logger.
            cache_logger_on_first_use=True,
        )

    else:
        # Configure logging level
        logging.basicConfig(level=get_settings().log_level.upper())


# Middleware to assign request_id and logger
class RequestIDLoggerMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, *, log_full: bool = True) -> None:
        super().__init__(app)
        self.log_full = log_full

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        request.state.request_id = request_id
        logger = structlog.stdlib.get_logger().bind(request_id=request_id)
        request.state.logger = logger

        # Exclude sensitive headers
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ["authorization"]}
        http_request = {}

        if self.log_full:
            # Read request body (works for JSON, not for form/multipart)
            body = await request.body()
            try:
                body_json = json.loads(body.decode()) if body else None
            except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError):
                body_json = None

            query_params = dict(request.query_params)
            # Do not remove logging - requirement SWR-15
            http_request = {
                "method": request.method,
                "url": str(request.url.path),
                "headers": headers,
                "body": body_json,
                "query_params": query_params,
            }

        else:
            http_request = {"method": request.method, "url": str(request.url), "headers": headers}

        # Do not remove logging - requirement SWR-15
        logger.info(
            "Request received",
            http_request=http_request,
        )

        start_time = time.perf_counter()
        response = await call_next(request)
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        try:
            res_body = [
                section async for section in response.body_iterator  # pyright: ignore[reportAttributeAccessIssue]
            ]
            response.body_iterator = iterate_in_threadpool(  # pyright: ignore[reportAttributeAccessIssue]
                iter(res_body)
            )

            # Stringified response body object
            res_body = res_body[0].decode()
        except Exception:  # noqa: BLE001
            res_body = None

        # IMPORTANT NOTE: The middlewares are waiting for the background tasks to finish, therefore the response time here is
        # not the actual time taken to respond to the client, but the time taken to process the request including background tasks.
        # Do not remove logging - requirement SWR-15
        logger.info(
            "Response sent",
            http_request=http_request,
            http_response={
                "status_code": response.status_code,
                "body": res_body,
                "processing_time": processing_time_ms,
            },
        )

        # Inject request_id into response headers
        response.headers["X-Request-ID"] = request_id

        return response


# always returns a logger, without context if necessary
def get_logger(request: Request = None) -> structlog.BoundLogger:  # pyright: ignore[reportArgumentType]
    if request:
        return request.state.logger
    try:
        ctx_request = request_context.get()
    except LookupError:
        return structlog.stdlib.get_logger()
    else:
        return ctx_request.state.logger


def get_request_id(request: Request = None) -> str | None:
    if request:
        return getattr(request.state, "request_id", None)
    try:
        ctx_request = request_context.get()
    except LookupError:
        return None
    else:
        return getattr(ctx_request.state, "request_id", None)


def test_logging() -> None:
    logger = get_logger()
    logger.debug("Test debug message")
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")
    logger.critical("Test critical message")
    try:
        1 / 0  # noqa: B018
    except ZeroDivisionError:
        logger.exception("Test exception logging")
