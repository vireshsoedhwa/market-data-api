import pytest
from httpx import AsyncClient


class TestGetHistory:
    async def test_returns_stub_history(self, client: AsyncClient):
        resp = await client.get(
            "/v1/history/NVDA",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["symbol"] == "NVDA"
        assert data["bars"] == []
        assert data["coverage"] == 0.0
        assert "stub" in data["provider_chain_used"]
        assert len(data["warnings"]) > 0

    async def test_symbol_is_uppercased(self, client: AsyncClient):
        resp = await client.get(
            "/v1/history/nvda",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "NVDA"

    async def test_missing_dates_returns_422(self, client: AsyncClient):
        resp = await client.get("/v1/history/NVDA")
        assert resp.status_code == 422

    async def test_invalid_date_format_returns_422(self, client: AsyncClient):
        resp = await client.get(
            "/v1/history/NVDA",
            params={"start_date": "not-a-date", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 422


class TestBatchHistory:
    async def test_returns_results_per_symbol(self, client: AsyncClient):
        resp = await client.post(
            "/v1/history/batch",
            json={
                "symbols": ["NVDA", "AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "timeframe": "1d",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "NVDA"
        assert data[1]["symbol"] == "AAPL"
