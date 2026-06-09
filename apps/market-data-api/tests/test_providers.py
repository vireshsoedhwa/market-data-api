from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestProvidersStatus:
    async def test_returns_providers_from_db(self, client: AsyncClient, mock_db_session: AsyncMock):
        """Verify the endpoint queries the DB and maps rows correctly."""
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

        resp = await client.get("/v1/providers/status")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["providers"]) == 1

        provider = data["providers"][0]
        assert provider["name"] == "finnhub"
        assert provider["display_name"] == "Finnhub"
        assert provider["is_enabled"] is True
        assert provider["status"] == "healthy"
        assert provider["supports_latest_price"] is True
        assert provider["supports_daily_history"] is False

    async def test_returns_empty_when_no_providers(self, client: AsyncClient, mock_db_session: AsyncMock):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result

        resp = await client.get("/v1/providers/status")
        assert resp.status_code == 200
        assert resp.json()["providers"] == []
