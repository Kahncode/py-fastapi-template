from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared.core.config import get_settings
from shared.core.logging import get_logger


# Pure ASGI middleware that catches unhandled exceptions and returns a 500 response
# Note that HTTPExceptions are not caught here and will be handled by FastAPI
class CatchExceptionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            logger = get_logger(Request(scope))
            logger.exception("Unhandled exception occurred")
            if response_started:
                # Too late to send an error response, let the server close the connection
                raise
            # Better than raise HTTPException here because it will return a JSON response with a more meaningful error message
            if get_settings().is_dev_environment():
                response = JSONResponse({"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                response = JSONResponse(
                    {"error": "Internal server error"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            await response(scope, receive, send)
