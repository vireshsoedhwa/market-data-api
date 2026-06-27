"""Tests for the provider router chain logic."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import ProviderError
from app.router.provider_router import get_daily_history, get_latest_price
from app.schemas.history import DailyPriceBarInternal
from app.schemas.quotes import LatestPriceInternal


def _make_price(symbol="AAPL", provider="finnhub", price="195.50"):
    return LatestPriceInternal(
        symbol=symbol,
        provider=provider,
        price=Decimal(price),
        currency="USD",
        as_of=datetime(2025, 6, 8, 20, 0, 0, tzinfo=timezone.utc),
        is_realtime=True,
        is_delayed=False,
    )


def _make_bars(symbol="AAPL", provider="tiingo"):
    return [
        DailyPriceBarInternal(
            symbol=symbol,
            provider=provider,
            date=date(2025, 6, 2),
            open=Decimal("190"),
            high=Decimal("195"),
            low=Decimal("189"),
            close=Decimal("194"),
            volume=50000,
            currency="USD",
        ),
    ]


class TestGetLatestPriceChain:
    async def test_returns_from_cache(self):
        """Cache hit should return immediately without calling providers."""
        cached = _make_price()
        with (
            patch("app.router.provider_router.get_cached_price", new_callable=AsyncMock, return_value=cached),
            patch("app.router.provider_router.get_latest_price_chain", return_value=["finnhub"]),
            patch("app.router.provider_router.get_provider") as mock_prov,
        ):
            result = await get_latest_price("AAPL")
        assert result.source_type == "cache"
        assert result.provider == "finnhub"
        mock_prov.assert_not_called()

    async def test_walks_chain_on_cache_miss(self):
        """Should call providers in order after cache miss."""
        mock_provider = MagicMock()
        mock_provider.supports_latest_price.return_value = True
        mock_provider.get_latest_price = AsyncMock(return_value=_make_price(provider="finnhub"))

        with (
            patch("app.router.provider_router.get_cached_price", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.set_cached_price", new_callable=AsyncMock),
            patch("app.router.provider_router.get_latest_price_chain", return_value=["finnhub"]),
            patch("app.router.provider_router.get_provider", return_value=mock_provider),
        ):
            result = await get_latest_price("AAPL")
        assert result.source_type == "provider"
        assert result.provider == "finnhub"
        assert result.data_status == "ok"

    async def test_skips_failed_provider(self):
        """If first provider fails, should try the next."""
        bad_provider = MagicMock()
        bad_provider.supports_latest_price.return_value = True
        bad_provider.get_latest_price = AsyncMock(side_effect=ProviderError("twelvedata", "AUTH_ERROR", "bad key"))

        good_provider = MagicMock()
        good_provider.supports_latest_price.return_value = True
        good_provider.get_latest_price = AsyncMock(return_value=_make_price(provider="finnhub"))

        def pick(name):
            return {"twelvedata": bad_provider, "finnhub": good_provider}[name]

        with (
            patch("app.router.provider_router.get_cached_price", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.set_cached_price", new_callable=AsyncMock),
            patch("app.router.provider_router.get_latest_price_chain", return_value=["twelvedata", "finnhub"]),
            patch("app.router.provider_router.get_provider", side_effect=pick),
        ):
            result = await get_latest_price("AAPL")
        assert result.provider == "finnhub"
        assert result.data_status == "ok"

    async def test_returns_stub_when_all_fail(self):
        """All providers failing should return stub with warnings."""
        bad = MagicMock()
        bad.supports_latest_price.return_value = True
        bad.get_latest_price = AsyncMock(side_effect=ProviderError("finnhub", "AUTH_ERROR", "bad key"))

        with (
            patch("app.router.provider_router.get_cached_price", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.get_latest_price_chain", return_value=["finnhub"]),
            patch("app.router.provider_router.get_provider", return_value=bad),
        ):
            result = await get_latest_price("AAPL")
        assert result.provider == "stub"
        assert result.data_status == "unavailable"
        assert any("finnhub" in w for w in result.warnings)


class TestGetDailyHistoryChain:
    async def test_returns_from_db_cache(self):
        """DB cache hit should return immediately without calling providers."""
        cached = _make_bars(provider="tiingo")
        with (
            patch("app.router.provider_router.get_cached_history", new_callable=AsyncMock, return_value=cached),
            patch("app.router.provider_router.get_daily_history_chain", return_value=["tiingo"]),
            patch("app.router.provider_router.get_provider") as mock_prov,
        ):
            result = await get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 2))
        assert len(result.bars) == 1
        assert result.provider_chain_used == ["tiingo"]
        mock_prov.assert_not_called()

    async def test_returns_bars_from_first_provider(self):
        mock_provider = MagicMock()
        mock_provider.supports_daily_history.return_value = True
        mock_provider.get_daily_history = AsyncMock(return_value=_make_bars())

        with (
            patch("app.router.provider_router.get_cached_history", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.store_history", new_callable=AsyncMock),
            patch("app.router.provider_router.get_daily_history_chain", return_value=["tiingo"]),
            patch("app.router.provider_router.get_provider", return_value=mock_provider),
        ):
            result = await get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 2))
        assert len(result.bars) == 1
        assert result.provider_chain_used == ["tiingo"]
        assert result.coverage > 0

    async def test_stores_bars_in_cache_after_provider_fetch(self):
        """After fetching from provider, bars should be stored in DB cache."""
        mock_provider = MagicMock()
        mock_provider.supports_daily_history.return_value = True
        mock_provider.get_daily_history = AsyncMock(return_value=_make_bars())

        mock_store = AsyncMock()
        with (
            patch("app.router.provider_router.get_cached_history", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.store_history", mock_store),
            patch("app.router.provider_router.get_daily_history_chain", return_value=["tiingo"]),
            patch("app.router.provider_router.get_provider", return_value=mock_provider),
        ):
            await get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 2))
        mock_store.assert_called_once()
        assert mock_store.call_args[0][0] == "AAPL"

    async def test_skips_empty_results(self):
        empty_provider = MagicMock()
        empty_provider.supports_daily_history.return_value = True
        empty_provider.get_daily_history = AsyncMock(return_value=[])

        good_provider = MagicMock()
        good_provider.supports_daily_history.return_value = True
        good_provider.get_daily_history = AsyncMock(return_value=_make_bars(provider="tiingo"))

        def pick(name):
            return {"fmp": empty_provider, "tiingo": good_provider}[name]

        with (
            patch("app.router.provider_router.get_cached_history", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.store_history", new_callable=AsyncMock),
            patch("app.router.provider_router.get_daily_history_chain", return_value=["fmp", "tiingo"]),
            patch("app.router.provider_router.get_provider", side_effect=pick),
        ):
            result = await get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 2))
        assert len(result.bars) == 1
        assert result.provider_chain_used == ["tiingo"]
        assert any("fmp" in w for w in result.warnings)

    async def test_returns_empty_when_all_fail(self):
        bad = MagicMock()
        bad.supports_daily_history.return_value = True
        bad.get_daily_history = AsyncMock(side_effect=ProviderError("tiingo", "AUTH_ERROR", "bad"))

        with (
            patch("app.router.provider_router.get_cached_history", new_callable=AsyncMock, return_value=None),
            patch("app.router.provider_router.get_daily_history_chain", return_value=["tiingo"]),
            patch("app.router.provider_router.get_provider", return_value=bad),
        ):
            result = await get_daily_history("AAPL", date(2025, 6, 2), date(2025, 6, 3))
        assert len(result.bars) == 0
        assert result.coverage == 0.0
        assert any("tiingo" in w for w in result.warnings)
