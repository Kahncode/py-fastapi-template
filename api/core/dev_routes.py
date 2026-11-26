from typing import Annotated

from fastapi import APIRouter, Depends, Security

from api.core.auth import authorize_api_key
from shared.services.service import get_service
from shared.services.sql_db import SQLDatabaseService

# TODO: If this router becomes available outside of development environment, it needs to be gated by admin/developer only API keys
router = APIRouter(tags=["dev"])


@router.get("/test/database")
async def test_database(
    db_service: Annotated[SQLDatabaseService, Depends(get_service(SQLDatabaseService))],
) -> bool:
    """Test database connection."""
    return await db_service.test_connection()


@router.get("/test/auth", dependencies=[Security(authorize_api_key)])
async def test_auth() -> None:
    """Test api key authentication (secured with Bearer auth)."""
    return
