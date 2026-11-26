"""
Background task wrapper example.

FastAPI runs background tasks after the response is sent: an exception raised there never reaches the client
and is easy to miss. `safe_task` wraps any sync or async task so failures are logged with their traceback.
"""

import inspect
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr

from shared.core.logging import get_logger

router = APIRouter(tags=["signup"])

# Pretend emails are sent through an external provider
sent_emails: set[str] = set()
# Addresses starting with this prefix are rejected by the pretend provider
BOUNCE_PREFIX = "bounce@"


async def safe_task(func: Callable, *args: object, **kwargs: object) -> None:
    """Run func (sync or async) as a background task, logging any exception instead of raising."""
    try:
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            await result
    except Exception:  # noqa: BLE001 - the response is already sent, so log the failure and keep the worker alive
        get_logger().exception("Background task failed", task=getattr(func, "__qualname__", repr(func)))


class SignupRequest(BaseModel):
    """Signup form payload."""

    email: EmailStr


async def send_welcome_email(email: str) -> None:
    """Pretend to send a welcome email, failing for addresses the provider rejects."""
    if email.startswith(BOUNCE_PREFIX):
        msg = f"Mail provider rejected {email}"
        raise RuntimeError(msg)
    sent_emails.add(email)


@router.post("/signup")
async def signup(background_tasks: BackgroundTasks, request: SignupRequest) -> dict[str, str]:
    """Queue the welcome email as a background task and return immediately."""
    background_tasks.add_task(safe_task, send_welcome_email, request.email)
    return {"status": "queued"}
