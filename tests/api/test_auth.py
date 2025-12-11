from http import HTTPStatus

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

from api.core.auth import authorize_api_key
from api.main import app

client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize(
    "keys",
    [
        ([(None, HTTPStatus.UNAUTHORIZED)]),  # no Authorization header
        ([("", HTTPStatus.UNAUTHORIZED)]),  # empty bearer token
        ([("VALID_API_KEY", HTTPStatus.OK)]),  # valid bearer token
    ],
)
async def test_auth(keys: list[tuple[str | None, HTTPStatus]]) -> None:
    for key, expected_status in keys:
        # Test the api_key_service directly
        bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=key if key else "")
        try:
            await authorize_api_key(bearer=bearer)
        except HTTPException as e:
            assert e.status_code == expected_status  # noqa: PT017
            continue
        else:
            assert expected_status == HTTPStatus.OK, f"Key: {key}, got {HTTPStatus.OK}, expected {expected_status}"

        # Test the auth route with each key
        url = "/dev/test/auth"
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        response = await client.get(url, headers=headers)
        assert (
            response.status_code == expected_status
        ), f"Key: {key}, got {response.status_code}, expected {expected_status}"
