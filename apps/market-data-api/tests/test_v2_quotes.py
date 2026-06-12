import pytest
from httpx import AsyncClient


class TestV2GetQuote:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/v2/quotes/NVDA")
        assert resp.status_code == 200

        data = resp.json()
        assert "request" in data
        assert "data" in data
        assert "meta" in data
        assert data["request"]["symbol"] == "NVDA"
        assert data["request"]["endpoint"] == "quotes"

    async def test_meta_includes_provider_info(self, client: AsyncClient):
        resp = await client.get("/v2/quotes/NVDA")
        meta = resp.json()["meta"]
        assert "provider" in meta
        assert "source_type" in meta
        assert "confidence" in meta
        assert "as_of" in meta
        assert "warnings" in meta

    async def test_symbol_is_uppercased(self, client: AsyncClient):
        resp = await client.get("/v2/quotes/nvda")
        assert resp.status_code == 200
        assert resp.json()["request"]["symbol"] == "NVDA"

    async def test_invalid_symbol_returns_400(self, client: AsyncClient):
        resp = await client.get("/v2/quotes/INVALID!!!")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_SYMBOL"

    async def test_symbol_too_long_returns_400(self, client: AsyncClient):
        resp = await client.get("/v2/quotes/AAAAAAAAAAAA")
        assert resp.status_code == 400

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/quotes/NVDA")
        assert resp.status_code == 401


class TestV2BatchQuotes:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.post(
            "/v2/quotes/batch",
            json={"symbols": ["NVDA", "AAPL"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["request"]["endpoint"] == "quotes/batch"
        assert len(data["data"]["quotes"]) == 2

    async def test_batch_too_large_returns_400(self, client: AsyncClient):
        symbols = [f"SYM{i}" for i in range(51)]
        resp = await client.post("/v2/quotes/batch", json={"symbols": symbols})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "BATCH_TOO_LARGE"

    async def test_invalid_symbol_in_batch_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/v2/quotes/batch",
            json={"symbols": ["NVDA", "BAD!!!"]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_SYMBOL"

    async def test_empty_batch(self, client: AsyncClient):
        resp = await client.post("/v2/quotes/batch", json={"symbols": []})
        assert resp.status_code == 200
        assert resp.json()["data"]["quotes"] == []
