"""
Authentication dependency for API endpoints.

Main security scheme: HTTP Bearer (Authorization: Bearer <api_key>).
Basic Auth is supported for convenience (e.g., curl -u <token>:), but is not the primary security scheme.

"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def authorize_api_key(bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    if not bearer or bearer.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    if len(bearer.credentials) == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
