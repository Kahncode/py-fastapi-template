from fastapi import APIRouter, Request
from pydantic import BaseModel
import os

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


class Version(BaseModel):
    name: str
    version: str


@router.get("/version", response_model=Version)
def version(request: Request):
    """
    Returns the global app name and version.
    """
    return {
        "name": request.app.title,
        "version": request.app.version,
    }
