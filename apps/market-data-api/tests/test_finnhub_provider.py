"""Tests for the Finnhub provider adapter using respx to mock HTTP."""

import pytest
import respx
from httpx import Response

from app.providers.base import ProviderError
from app.providers.finnhub import FinnhubProvider

QUOTE_URL = "https://finnhub.io/api/v1/quote"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr("app.providers.finnhub.settings.finnhub_api_key", "test-key")
    return FinnhubProvider()


class TestFinnhubLatestPrice:
    @respx.mock
    async def test_returns_price(self, provider):
        respx.get(QUOTE_URL).mock(
            return_value=Response(
                200,
                json={"c": 125.50, "d": 1.25, "dp": 1.0, "h": 126, "l": 124, "o": 124.5, "pc": 124.25, "t": 1700000000},
            )
        )
        result = await provider.get_latest_price("AAPL")
        assert result.symbol == "AAPL"
        assert result.provider == "finnhub"
        assert float(result.price) == 125.50
        assert result.is_delayed is True
        assert result.delay_minutes == 15

    @respx.mock
    async def test_unknown_symbol_raises(self, provider):
        respx.get(QUOTE_URL).mock(
            return_value=Response(200, json={"c": 0, "d": None, "dp": None, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0})
        )
        with pytest.raises(ProviderError, match="SYMBOL_NOT_FOUND"):
            await provider.get_latest_price("ZZZZZZ")

    @respx.mock
    async def test_rate_limit_raises(self, provider):
        respx.get(QUOTE_URL).mock(return_value=Response(429, text="Rate limited"))
        with pytest.raises(ProviderError, match="RATE_LIMITED"):
            await provider.get_latest_price("AAPL")

    @respx.mock
    async def test_http_error_raises(self, provider):
        respx.get(QUOTE_URL).mock(return_value=Response(500, text="Internal Server Error"))
        with pytest.raises(ProviderError, match="HTTP_ERROR"):
            await provider.get_latest_price("AAPL")

    async def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.setattr("app.providers.finnhub.settings.finnhub_api_key", "")
        prov = FinnhubProvider()
        with pytest.raises(ProviderError, match="NO_API_KEY"):
            await prov.get_latest_price("AAPL")

    def test_supports_latest_price(self, provider):
        assert provider.supports_latest_price() is True

    def test_does_not_support_history(self, provider):
        assert provider.supports_daily_history() is False
