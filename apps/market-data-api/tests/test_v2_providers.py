from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestV2ProvidersStatus:
    async def test_returns_envelope(self, client: AsyncClient, mock_db_session: AsyncMock):
        mock_row = MagicMock()
        mock_row.name = "finnhub"
        mock_row.display_name = "Finnhub"
        mock_row.is_enabled = True
        mock_row.supports_latest_price = True
        mock_row.supports_daily_history = False
        mock_row.health_status = "healthy"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        resp = await client.get("/v2/providers/status")
        assert resp.status_code == 200

        data = resp.json()
        assert "request" in data
        assert "data" in data
        assert "meta" in data
        assert data["request"]["endpoint"] == "providers/status"
        assert len(data["data"]["providers"]) == 1
        assert data["data"]["providers"][0]["name"] == "finnhub"

    async def test_requires_auth(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get("/v2/providers/status")
        assert resp.status_code == 401
