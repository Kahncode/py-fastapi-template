from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = request_context.set(request)
        try:
            response = await call_next(request)
        finally:
            request_context.reset(token)
        return response


# Context variable to hold the current request context
request_context: ContextVar = ContextVar("request_context")
