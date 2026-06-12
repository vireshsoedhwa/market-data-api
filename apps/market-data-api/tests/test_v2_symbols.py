import pytest
from httpx import AsyncClient


class TestV2SymbolSearch:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/v2/symbols/search", params={"query": "nvda"})
        assert resp.status_code == 200

        data = resp.json()
        assert "request" in data
        assert "data" in data
        assert "meta" in data
        assert data["request"]["endpoint"] == "symbols/search"
        assert data["data"]["results"] == []

    async def test_missing_query_returns_422(self, client: AsyncClient):
        resp = await client.get("/v2/symbols/search")
        assert resp.status_code == 422

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/symbols/search", params={"query": "nvda"})
        assert resp.status_code == 401


class TestV2SymbolMetadata:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/v2/symbols/NVDA/metadata")
        assert resp.status_code == 200

        data = resp.json()
        assert data["data"]["symbol"] == "NVDA"
        assert data["request"]["endpoint"] == "symbols/metadata"

    async def test_symbol_is_uppercased(self, client: AsyncClient):
        resp = await client.get("/v2/symbols/nvda/metadata")
        assert resp.status_code == 200
        assert resp.json()["data"]["symbol"] == "NVDA"

    async def test_invalid_symbol_returns_400(self, client: AsyncClient):
        resp = await client.get("/v2/symbols/BAD!!!/metadata")
        assert resp.status_code == 400

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/symbols/NVDA/metadata")
        assert resp.status_code == 401
