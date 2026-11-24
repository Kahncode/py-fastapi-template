from contextvars import ContextVar

from starlette.requests import HTTPConnection, Request
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestContextMiddleware:
    """
    Pure ASGI middleware exposing the current request through `request_context`.

    Unlike BaseHTTPMiddleware, it runs the app in the same task/context, so the value stays set for the
    whole response lifetime (streaming, background tasks) and covers WebSocket connections.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Request.state is backed by scope["state"], so it is shared with every other Request built from this scope
        # Request only accepts http scopes, HTTPConnection is its base class and supports both
        connection = Request(scope, receive) if scope["type"] == "http" else HTTPConnection(scope)
        token = request_context.set(connection)
        try:
            await self.app(scope, receive, send)
        finally:
            request_context.reset(token)


# Context variable to hold the current request context. No default: callers handle LookupError outside of a request.
request_context: ContextVar[HTTPConnection] = ContextVar("request_context")
