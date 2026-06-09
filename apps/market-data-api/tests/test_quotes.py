import pytest
from httpx import AsyncClient


class TestGetQuote:
    async def test_returns_stub_quote(self, client: AsyncClient):
        resp = await client.get("/v1/quotes/NVDA")
        assert resp.status_code == 200

        data = resp.json()
        assert data["symbol"] == "NVDA"
        assert data["provider"] == "stub"
        assert data["data_status"] == "unavailable"
        assert data["currency"] == "USD"
        assert len(data["warnings"]) > 0

    async def test_symbol_is_uppercased(self, client: AsyncClient):
        resp = await client.get("/v1/quotes/nvda")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "NVDA"

    async def test_exchange_query_param(self, client: AsyncClient):
        resp = await client.get("/v1/quotes/SHOP", params={"exchange": "TSX"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["symbol"] == "SHOP"
        assert data["exchange"] == "TSX"


class TestBatchQuotes:
    async def test_returns_multiple_quotes(self, client: AsyncClient):
        resp = await client.post(
            "/v1/quotes/batch",
            json={"symbols": ["NVDA", "AAPL", "IONQ"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["quotes"]) == 3
        symbols = [q["symbol"] for q in data["quotes"]]
        assert symbols == ["NVDA", "AAPL", "IONQ"]
        assert data["errors"] == []

    async def test_empty_symbols_list(self, client: AsyncClient):
        resp = await client.post("/v1/quotes/batch", json={"symbols": []})
        assert resp.status_code == 200
        assert resp.json()["quotes"] == []
