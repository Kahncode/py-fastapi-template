from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from shared.core.config import get_settings
from shared.core.logging import get_logger


# This middleware catches unhandled exceptions and returns a 500 response
# Note that HTTPExceptions are not caught here and will be handled by FastAPI
class CatchExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            logger = get_logger(request)
            logger.exception("Unhandled exception occurred")
            # Better than raise HTTPException here because it will return a JSON response with a more meaningful error message
            if get_settings().is_dev_environment():
                return JSONResponse({"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return JSONResponse(
                    {"error": "Internal server error"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
