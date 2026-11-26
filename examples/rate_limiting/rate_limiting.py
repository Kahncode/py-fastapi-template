"""
In-memory rate limiting dependency example.

Sliding window per client IP, enforced as a route dependency. State is kept per process: for multi-worker
or multi-replica deployments, back this with a shared store (e.g. Redis) instead.
"""

import math
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter(tags=["limited"])


class RateLimiter:
    """Sliding-window rate limiter: at most `max_requests` per `window_seconds` per client."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request) -> None:
        now = time.monotonic()
        hits = self._hits[self._client_key(request)]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            retry_after = max(1, math.ceil(self.window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


# Demo route: 5 requests per 10 seconds per client
limiter = RateLimiter(max_requests=5, window_seconds=10.0)


@router.get("/limited")
async def limited_endpoint(_limiter: Annotated[None, Depends(limiter)]) -> dict[str, str]:
    """Route guarded by the module-level limiter."""
    return {"status": "ok"}
