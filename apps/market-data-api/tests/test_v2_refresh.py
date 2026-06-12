import pytest
from httpx import AsyncClient


class TestV2Refresh:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.post(
            "/v2/refresh",
            json={"symbols": ["NVDA", "AAPL"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "request" in data
        assert "data" in data
        assert "meta" in data
        assert data["data"]["status"] == "queued"
        assert data["data"]["symbols_queued"] == ["NVDA", "AAPL"]
        assert data["data"]["job_id"].startswith("refresh_")

    async def test_validates_symbols(self, client: AsyncClient):
        resp = await client.post(
            "/v2/refresh",
            json={"symbols": ["BAD!!!"]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_SYMBOL"

    async def test_batch_too_large(self, client: AsyncClient):
        symbols = [f"SYM{i}" for i in range(51)]
        resp = await client.post("/v2/refresh", json={"symbols": symbols})
        assert resp.status_code == 400

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.post(
            "/v2/refresh",
            json={"symbols": ["NVDA"]},
        )
        assert resp.status_code == 401


class TestV2JobStatus:
    async def test_returns_envelope(self, client: AsyncClient):
        resp = await client.get("/v2/jobs/refresh_abc123")
        assert resp.status_code == 200

        data = resp.json()
        assert data["data"]["job_id"] == "refresh_abc123"
        assert data["data"]["status"] == "unknown"
        assert data["request"]["endpoint"] == "jobs"

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/jobs/refresh_abc123")
        assert resp.status_code == 401
