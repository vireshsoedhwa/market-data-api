"""Tests for the Tiingo provider adapter using respx to mock HTTP."""

from datetime import date

import pytest
import respx
from httpx import Response

from app.providers.base import ProviderError
from app.providers.tiingo import TiingoProvider

HISTORY_URL = "https://api.tiingo.com/tiingo/daily/aapl/prices"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr("app.providers.tiingo.settings.tiingo_api_key", "test-key")
    return TiingoProvider()


class TestTiingoDailyHistory:
    @respx.mock
    async def test_returns_bars(self, provider):
        respx.get(HISTORY_URL).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "adjClose": 194.0,
                        "adjHigh": 195.0,
                        "adjLow": 189.0,
                        "adjOpen": 190.0,
                        "adjVolume": 50000,
                        "close": 194.0,
                        "date": "2025-06-02T00:00:00+00:00",
                        "divCash": 0.0,
                        "high": 195.0,
                        "low": 189.0,
                        "open": 190.0,
                        "splitFactor": 1.0,
                        "volume": 50000,
                    },
                    {
                        "adjClose": 195.0,
                        "adjHigh": 196.0,
                        "adjLow": 193.0,
                        "adjOpen": 194.0,
                        "adjVolume": 60000,
                        "close": 195.0,
                        "date": "2025-06-03T00:00:00+00:00",
                        "divCash": 0.0,
                        "high": 196.0,
                        "low": 193.0,
                        "open": 194.0,
                        "splitFactor": 1.0,
                        "volume": 60000,
                    },
                ],
            )
        )
        bars = await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))
        assert len(bars) == 2
        assert bars[0].symbol == "AAPL"
        assert bars[0].provider == "tiingo"
        assert bars[0].date == date(2025, 6, 2)
        assert float(bars[0].close) == 194.0
        assert float(bars[0].adjusted_close) == 194.0
        assert bars[0].volume == 50000
        assert bars[1].date == date(2025, 6, 3)
        assert float(bars[1].close) == 195.0

    @respx.mock
    async def test_auth_error_raises(self, provider):
        respx.get(HISTORY_URL).mock(return_value=Response(401, json={"detail": "Not authorized"}))
        with pytest.raises(ProviderError, match="AUTH_ERROR"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    @respx.mock
    async def test_not_found_raises(self, provider):
        respx.get(HISTORY_URL).mock(return_value=Response(404, json={"detail": "Not found"}))
        with pytest.raises(ProviderError, match="SYMBOL_NOT_FOUND"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    @respx.mock
    async def test_rate_limited_raises(self, provider):
        respx.get(HISTORY_URL).mock(return_value=Response(429, json={"detail": "Rate limited"}))
        with pytest.raises(ProviderError, match="RATE_LIMITED"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    @respx.mock
    async def test_http_error_raises(self, provider):
        respx.get(HISTORY_URL).mock(return_value=Response(500, text="Server Error"))
        with pytest.raises(ProviderError, match="HTTP_ERROR"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    @respx.mock
    async def test_unexpected_format_raises(self, provider):
        respx.get(HISTORY_URL).mock(return_value=Response(200, json={"not": "a list"}))
        with pytest.raises(ProviderError, match="PARSE_ERROR"):
            await provider.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    async def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.setattr("app.providers.tiingo.settings.tiingo_api_key", "")
        prov = TiingoProvider()
        with pytest.raises(ProviderError, match="NO_API_KEY"):
            await prov.get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))

    def test_supports_history_only(self, provider):
        assert provider.supports_latest_price() is False
        assert provider.supports_daily_history() is True

    async def test_latest_price_not_supported(self, provider):
        with pytest.raises(ProviderError, match="NOT_SUPPORTED"):
            await provider.get_latest_price("AAPL")
