"""
JWT authentication example using the OAuth2 password flow.

- POST /login verifies credentials and returns a short-lived access token (HS256).
- GET /me requires a bearer token and returns the user it names.

The secret, algorithm and TTL are constants here for simplicity. In a real application, load the secret
from settings or a mounted secret, as shown in the template's configuration framework.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

router = APIRouter(tags=["auth"])

SECRET_KEY = "example-secret-do-not-use-in-production"  # noqa: S105 - demo credential, see module docstring
ALGORITHM = "HS256"
TOKEN_TTL = timedelta(minutes=30)
_PBKDF2_ITERATIONS = 100_000

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


@dataclass
class _User:
    """Demo user record."""

    salt: bytes
    password_hash: bytes
    role: str


def _hash_password(password: str, salt: bytes) -> bytes:
    """Hash a password with PBKDF2-SHA256 (demo-grade: for real apps use argon2 or bcrypt)."""
    return pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)


# Demo user store
USERS = {
    "alice": _User(salt=b"alice-salt", password_hash=_hash_password("wonderland", b"alice-salt"), role="admin"),
    "bob": _User(salt=b"bob-salt", password_hash=_hash_password("builder", b"bob-salt"), role="user"),
}


def create_access_token(subject: str, expires_delta: timedelta = TOKEN_TTL) -> str:
    """Create a signed JWT naming the subject, expiring after expires_delta."""
    payload = {"sub": subject, "exp": datetime.now(UTC) + expires_delta}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class CurrentUser(BaseModel):
    """Authenticated user resolved from a valid token."""

    username: str
    role: str


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    """Validate the bearer token and resolve the user it names."""
    try:
        username: str | None = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"}
        ) from err

    user_record = USERS.get(username) if username else None
    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user", headers={"WWW-Authenticate": "Bearer"}
        )
    return CurrentUser(username=username, role=user_record.role)


@router.post("/login")
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
    """Verify credentials and return a bearer access token."""
    user_record = USERS.get(form.username)
    if not user_record or not compare_digest(
        _hash_password(form.password, user_record.salt), user_record.password_hash
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    return {"access_token": create_access_token(form.username), "token_type": "bearer"}


@router.get("/me")
async def me(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """Return the authenticated user."""
    return current_user
