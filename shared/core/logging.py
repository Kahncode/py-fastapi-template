import json
import logging
import sys
import time
import uuid

import structlog
from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


# Response bodies larger than this are not logged (they are always streamed through untouched)
MAX_LOGGED_RESPONSE_BODY_BYTES = 64 * 1024


async def _buffer_request_body(receive: Receive) -> tuple[Receive, bytes]:
    """Read the whole request body and return it with a `receive` that replays it to the downstream app."""
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break  # client disconnected
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    body = b"".join(chunks)
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay, body


# Pure ASGI middleware to assign request_id and logger
class RequestIDLoggerMiddleware:

    def __init__(self, app: ASGIApp, *, log_full: bool = True) -> None:
        self.app = app
        self.log_full = log_full

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        request.state.request_id = request_id
        logger = structlog.stdlib.get_logger().bind(request_id=request_id)
        request.state.logger = logger

        # Exclude sensitive headers
        headers = {k: v for k, v in request.headers.items() if k.lower() != "authorization"}
        http_request = {}

        if self.log_full:
            # Read request body (works for JSON, not for form/multipart) and replay it for the app
            receive, body = await _buffer_request_body(receive)
            try:
                body_json = json.loads(body.decode()) if body else None
            except json.JSONDecodeError, UnicodeDecodeError, RuntimeError:
                body_json = None

            query_params = dict(request.query_params)
            http_request = {
                "method": request.method,
                "url": str(request.url.path),
                "headers": headers,
                "body": body_json,
                "query_params": query_params,
            }

        else:
            http_request = {"method": request.method, "url": str(request.url), "headers": headers}

        logger.info(
            "Request received",
            http_request=http_request,
        )

        start_time = time.perf_counter()
        status_code = 0
        processing_time_ms = 0
        body_chunks: list[bytes] = []
        body_size = 0
        body_truncated = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, processing_time_ms, body_size, body_truncated
            if message["type"] == "http.response.start":
                status_code = message["status"]
                processing_time_ms = int((time.perf_counter() - start_time) * 1000)
                # Inject request_id into response headers
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            elif message["type"] == "http.response.body" and not body_truncated:
                chunk = message.get("body", b"")
                body_size += len(chunk)
                if body_size > MAX_LOGGED_RESPONSE_BODY_BYTES:
                    body_truncated = True
                    body_chunks.clear()
                else:
                    body_chunks.append(chunk)
            await send(message)

        await self.app(scope, receive, send_wrapper)

        # Stringified response body object, None if empty, too large or not text
        res_body: str | None
        try:
            res_body = None if body_truncated else (b"".join(body_chunks).decode() or None)
        except UnicodeDecodeError:
            res_body = None

        # IMPORTANT NOTE: This is logged once the app has fully returned (body streamed, background tasks done), but
        # processing_time is measured up to the start of the response, i.e. the time taken to produce it.
        logger.info(
            "Response sent",
            http_request=http_request,
            http_response={
                "status_code": status_code,
                "body": res_body,
                "processing_time": processing_time_ms,
            },
        )


# always returns a logger, without context if necessary
def get_logger(request: Request = None) -> structlog.BoundLogger:  # pyright: ignore[reportArgumentType]
    if request:
        return request.state.logger
    try:
        ctx_request = request_context.get()
    except LookupError:
        return structlog.stdlib.get_logger()
    else:
        # No logger is bound for connections the logging middleware skips, such as WebSockets
        return getattr(ctx_request.state, "logger", None) or structlog.stdlib.get_logger()


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
