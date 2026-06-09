"""Tests for the Massive provider adapter using respx to mock HTTP."""

from datetime import date

import pytest
import respx
from httpx import Response

from app.providers.base import ProviderError
from app.providers.massive import MassiveProvider

SNAPSHOT_URL = "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL"
BARS_URL = "https://api.massive.com/v2/aggs/ticker/AAPL/range/1/day/2025-06-02/2025-06-03"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr("app.providers.massive.settings.massive_api_key", "test-key")
    return MassiveProvider()


class TestMassiveLatestPrice:
    @respx.mock
    async def test_returns_price(self, provider):
        respx.get(SNAPSHOT_URL).mock(
            return_value=Response(
                200,
                json={
                    "status": "OK",
                    "request_id": "abc123",
                    "ticker": {
                        "ticker": "AAPL",
                        "lastTrade": {"p": 195.25, "s": 100, "t": 1749412800000000000},
                        "day": {"o": 194.0, "h": 196.0, "l": 193.5, "c": 195.25, "v": 50000000},
                        "prevDay": {"o": 193.0, "h": 195.0, "l": 192.0, "c": 194.0, "v": 45000000},
                    },
                },
            )
        )
        result = await provider.get_latest_price("AAPL")
        assert result.symbol == "AAPL"
        assert result.provider == "massive"
        assert float(result.price) == 195.25
        assert result.is_realtime is True

    @respx.mock
    async def test_auth_error_raises(self, provider):
        respx.get(SNAPSHOT_URL).mock(return_value=Response(401, json={"error": "unauthorized"}))
        with pytest.raises(ProviderError, match="AUTH_ERROR"):
            await provider.get_latest_price("AAPL")

    @respx.mock
    async def test_not_found_raises(self, provider):
        respx.get(SNAPSHOT_URL).mock(return_value=Response(404, json={"error": "not found"}))
        with pytest.raises(ProviderError, match="SYMBOL_NOT_FOUND"):
            await provider.get_latest_price("AAPL")

    @respx.mock
    async def test_rate_limited_raises(self, provider):
        respx.get(SNAPSHOT_URL).mock(return_value=Response(429, json={"error": "rate limited"}))
        with pytest.raises(ProviderError, match="RATE_LIMITED"):
            await provider.get_latest_price("AAPL")

    async def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.setattr("app.providers.massive.settings.massive_api_key", "")
        prov = MassiveProvider()
        with pytest.raises(ProviderError, match="NO_API_KEY"):
            await prov.get_latest_price("AAPL")


class TestMassiveDailyHistory:
    @respx.mock
    async def test_returns_bars(self, provider):
        respx.get(BARS_URL).mock(
            return_value=Response(
                200,
                json={
                    "status": "OK",
                    "ticker": "AAPL",
                    "resultsCount": 2,
                    "results": [
                        {"t": 1748822400000, "o": 190.0, "h": 195.0, "l": 189.0, "c": 194.0, "v": 50000, "n": 1000, "vw": 192.5},
                        {"t": 1748908800000, "o": 194.0, "h": 196.0, "l": 193.0, "c": 195.0, "v": 60000, "n": 1200, "vw": 194.5},
                    ],
                },
            )
        )
        bars = await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))
        assert len(bars) == 2
        assert bars[0].symbol == "AAPL"
        assert bars[0].date == date(2025, 6, 2)
        assert float(bars[0].close) == 194.0
        assert bars[1].date == date(2025, 6, 3)

    @respx.mock
    async def test_http_error_raises(self, provider):
        respx.get(BARS_URL).mock(return_value=Response(500, text="Server Error"))
        with pytest.raises(ProviderError, match="HTTP_ERROR"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    def test_supports_both(self, provider):
        assert provider.supports_latest_price() is True
        assert provider.supports_daily_history() is True
