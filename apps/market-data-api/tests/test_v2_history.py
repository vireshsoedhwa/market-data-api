import pytest
from httpx import AsyncClient


class TestV2GetHistory:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.get(
            "/v2/history/NVDA",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "request" in data
        assert "data" in data
        assert "meta" in data
        assert data["request"]["symbol"] == "NVDA"
        assert data["request"]["endpoint"] == "history"

    async def test_invalid_symbol_returns_400(self, client: AsyncClient):
        resp = await client.get(
            "/v2/history/BAD!!!",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_SYMBOL"

    async def test_start_after_end_returns_400(self, client: AsyncClient):
        resp = await client.get(
            "/v2/history/NVDA",
            params={"start_date": "2024-12-31", "end_date": "2024-01-01"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DATE_RANGE"

    async def test_future_date_returns_400(self, client: AsyncClient):
        resp = await client.get(
            "/v2/history/NVDA",
            params={"start_date": "2024-01-01", "end_date": "2099-01-01"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DATE_RANGE"

    async def test_missing_dates_returns_422(self, client: AsyncClient):
        resp = await client.get("/v2/history/NVDA")
        assert resp.status_code == 422

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get(
            "/v2/history/NVDA",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 401


class TestV2BatchHistory:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.post(
            "/v2/history/batch",
            json={
                "symbols": ["NVDA", "AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["request"]["endpoint"] == "history/batch"
        assert len(data["data"]) == 2

    async def test_batch_too_large_returns_400(self, client: AsyncClient):
        symbols = [f"SYM{i}" for i in range(51)]
        resp = await client.post(
            "/v2/history/batch",
            json={
                "symbols": symbols,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "BATCH_TOO_LARGE"
