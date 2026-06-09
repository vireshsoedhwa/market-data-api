import pytest
from httpx import AsyncClient


class TestSymbolSearch:
    async def test_returns_empty_results(self, client: AsyncClient):
        resp = await client.get("/v1/symbols/search", params={"query": "nvda"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    async def test_missing_query_returns_422(self, client: AsyncClient):
        resp = await client.get("/v1/symbols/search")
        assert resp.status_code == 422


class TestSymbolMetadata:
    async def test_returns_metadata(self, client: AsyncClient):
        resp = await client.get("/v1/symbols/NVDA/metadata")
        assert resp.status_code == 200

        data = resp.json()
        assert data["symbol"] == "NVDA"

    async def test_symbol_is_uppercased(self, client: AsyncClient):
        resp = await client.get("/v1/symbols/nvda/metadata")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "NVDA"
