import pytest
from httpx import AsyncClient


class TestSecurityHeaders:
    async def test_nosniff_header_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    async def test_frame_deny_header_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    async def test_cache_control_header_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("cache-control") == "no-store"

    async def test_headers_on_v2_endpoints(self, client: AsyncClient):
        resp = await client.get("/v2/capabilities")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
