"""Tests for the Redis cache layer."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.cache.latest_price_cache import get_cached_price, set_cached_price
from app.schemas.quotes import LatestPriceInternal

SAMPLE_PRICE = LatestPriceInternal(
    symbol="AAPL",
    provider="finnhub",
    price=Decimal("195.50"),
    currency="USD",
    as_of=datetime(2025, 6, 8, 20, 0, 0, tzinfo=timezone.utc),
    is_realtime=False,
    is_delayed=True,
    delay_minutes=15,
)


class TestGetCachedPrice:
    async def test_returns_none_on_miss(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        with patch("app.cache.latest_price_cache._get_redis", return_value=mock_redis):
            result = await get_cached_price("AAPL")
        assert result is None
        mock_redis.get.assert_awaited_once_with("quote:AAPL")

    async def test_returns_price_on_hit(self):
        payload = SAMPLE_PRICE.model_dump(mode="json")
        payload["price"] = str(payload["price"])
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(payload)
        with patch("app.cache.latest_price_cache._get_redis", return_value=mock_redis):
            result = await get_cached_price("AAPL")
        assert result is not None
        assert result.symbol == "AAPL"
        assert result.provider == "finnhub"

    async def test_returns_none_on_error(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")
        with patch("app.cache.latest_price_cache._get_redis", return_value=mock_redis):
            result = await get_cached_price("AAPL")
        assert result is None


class TestSetCachedPrice:
    async def test_writes_to_redis(self):
        mock_redis = AsyncMock()
        with patch("app.cache.latest_price_cache._get_redis", return_value=mock_redis):
            await set_cached_price(SAMPLE_PRICE)
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "quote:AAPL"
        stored = json.loads(call_args[0][1])
        assert stored["symbol"] == "AAPL"
        assert stored["provider"] == "finnhub"

    async def test_swallows_error(self):
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = ConnectionError("Redis down")
        with patch("app.cache.latest_price_cache._get_redis", return_value=mock_redis):
            # Should not raise
            await set_cached_price(SAMPLE_PRICE)
