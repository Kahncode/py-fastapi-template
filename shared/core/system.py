import asyncio
import os
import platform

import cpuinfo
from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel

from shared.core.app_environment import AppEnvironment, get_environment_suffix
from shared.core.config import get_settings
from shared.core.logging import test_logging as test_logging_function

router = APIRouter(tags=["system"])


@router.head("/healthz")
@router.head("/health")
@router.get("/health")
@router.get("/healthz")
def health() -> dict:
    """
    Health check endpoint for the API.

    Returns a simple status response indicating that the service is running.
    """
    return {"status": "ok"}


class Version(BaseModel):
    name: str
    version: str


@router.get("/version")
def version(request: Request) -> Version:
    """Return the global app name and version."""
    # Note: this could also be fetched directly from settings
    return Version(name=request.app.title, version=request.app.version)


dev_router = APIRouter(tags=["dev"])


@dev_router.get("/environment")
def get_environment() -> dict:
    """Return the current environment variables."""
    return dict(os.environ)


@dev_router.post("/sleep")
async def sleep(delay_ms: int) -> None:
    """
    Sleep for delay ms then returns.

    Useful to test latency, load and scaling behavior.
    """
    await asyncio.sleep(delay_ms / 1000)


@dev_router.post("/test/logging")
async def test_logging() -> None:
    """Test logging."""
    test_logging_function()


@dev_router.get("/cpuinfo")
async def get_cpu_info() -> dict:
    """Return cpu information."""
    return cpuinfo.get_cpu_info()


@dev_router.get("/platform")
async def get_platform_info() -> dict:
    """Return platform information."""

    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def configure_fastapi(app: FastAPI) -> None:
    """Configure a FastAPI app instance based on settings."""
    settings = get_settings()
    # Enable docs only in development
    dev_enabled: bool = settings.is_dev_environment()
    # Adds the URL of the server in docs based on environment. Keep this for prod as well so we can always generate correct docs.
    if settings.app_environment != AppEnvironment.LOCAL:
        app.servers = [
            {
                "url": f"https://api{get_environment_suffix(settings.app_environment)}.example.com",
                "description": f"{settings.app_name} Server ({settings.app_environment.value})",
            }
        ]

    app.title = settings.app_name
    app.version = str(settings.app_version)
    app.docs_url = "/docs" if dev_enabled else None
    app.redoc_url = "/redoc" if dev_enabled else None
    app.openapi_url = "/openapi.json" if dev_enabled else None

    app.include_router(router)
    if dev_enabled:
        app.include_router(dev_router, prefix="/dev")
