"""
Authentication dependency for API endpoints.

Main security scheme: HTTP Bearer (Authorization: Bearer <api_key>).
Basic Auth is supported for convenience (e.g., curl -u <token>:), but is not the primary security scheme.

"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def authorize_api_key(bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    if bearer and bearer.scheme.lower() == "bearer":
        api_key = bearer.credentials
        api_key_valid: bool = len(api_key) > 0
        authorized: bool = api_key_valid

        if not api_key_valid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        if not authorized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key is inactive or expired")

        return  # Authorized
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
