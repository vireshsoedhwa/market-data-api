import pytest
from httpx import AsyncClient


class TestRefresh:
    async def test_queues_refresh(self, client: AsyncClient):
        resp = await client.post(
            "/v1/refresh",
            json={"symbols": ["NVDA", "AAPL"]},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "queued"
        assert data["symbols_queued"] == ["NVDA", "AAPL"]
        assert data["job_id"].startswith("refresh_")

    async def test_refresh_with_data_types(self, client: AsyncClient):
        resp = await client.post(
            "/v1/refresh",
            json={
                "symbols": ["NVDA"],
                "data_types": ["latest_price"],
                "priority": "high",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["symbols_queued"] == ["NVDA"]

    async def test_refresh_empty_symbols_returns_200(self, client: AsyncClient):
        resp = await client.post("/v1/refresh", json={"symbols": []})
        assert resp.status_code == 200
        assert resp.json()["symbols_queued"] == []


class TestJobStatus:
    async def test_returns_job_status(self, client: AsyncClient):
        resp = await client.get("/v1/jobs/refresh_abc123")
        assert resp.status_code == 200

        data = resp.json()
        assert data["job_id"] == "refresh_abc123"
        assert data["status"] == "unknown"
