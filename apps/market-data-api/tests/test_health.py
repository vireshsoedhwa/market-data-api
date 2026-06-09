import pytest
from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "market-data-api"
    assert data["version"] == "0.1.0"


async def test_health_is_public(unauthed_client: AsyncClient):
    """Health endpoint should not require authentication."""
    resp = await unauthed_client.get("/health")
    assert resp.status_code == 200
