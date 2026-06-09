import pytest
from httpx import AsyncClient


async def test_missing_auth_returns_401(unauthed_client: AsyncClient):
    """Requests without a Bearer token should be rejected."""
    resp = await unauthed_client.get("/v1/quotes/NVDA")
    assert resp.status_code == 401


async def test_invalid_token_returns_401(unauthed_client: AsyncClient):
    """Requests with a wrong token should be rejected."""
    resp = await unauthed_client.get(
        "/v1/quotes/NVDA",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


async def test_valid_token_returns_200(client: AsyncClient):
    """Requests with a valid token should succeed."""
    resp = await client.get("/v1/quotes/NVDA")
    assert resp.status_code == 200
