import pytest
from httpx import AsyncClient


class TestCapabilities:
    async def test_returns_capabilities(self, client: AsyncClient):
        resp = await client.get("/v2/capabilities")
        assert resp.status_code == 200

        data = resp.json()
        assert data["version"] == "2.0.0"
        assert "quotes" in data["endpoints"]
        assert "history" in data["endpoints"]
        assert "symbols" in data["endpoints"]
        assert "refresh" in data["endpoints"]
        assert data["max_batch_size"] == 50
        assert "1d" in data["supported_timeframes"]
        assert data["rate_limits"]["requests_per_minute"] == 120
        assert data["rate_limits"]["batch_max_symbols"] == 50
        assert data["authentication"]["type"] == "bearer"
        assert data["authentication"]["header"] == "Authorization"

    async def test_data_freshness_included(self, client: AsyncClient):
        resp = await client.get("/v2/capabilities")
        data = resp.json()
        assert "latest_price" in data["data_freshness"]
        assert "daily_history" in data["data_freshness"]
        assert data["data_freshness"]["latest_price"]["typical_delay"] == "15min"

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/capabilities")
        assert resp.status_code == 401


class TestTools:
    async def test_returns_tool_definitions(self, client: AsyncClient):
        resp = await client.get("/v2/tools")
        assert resp.status_code == 200

        data = resp.json()
        assert "tools" in data
        tools = data["tools"]
        assert len(tools) == 4

        names = [t["function"]["name"] for t in tools]
        assert "get_latest_price" in names
        assert "get_daily_history" in names
        assert "search_symbols" in names
        assert "refresh_data" in names

    async def test_tool_format_is_openai_compatible(self, client: AsyncClient):
        resp = await client.get("/v2/tools")
        tools = resp.json()["tools"]

        for tool in tools:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/tools")
        assert resp.status_code == 401
