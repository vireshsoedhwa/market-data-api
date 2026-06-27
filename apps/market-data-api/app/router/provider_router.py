"""
Provider router — resolves latest prices and daily history by iterating
through the configured provider chain with fallback logic.

For each request the router:
1. Checks the Redis cache (latest-price only).
2. Walks the provider chain in order, skipping providers that lack an API key.
3. Returns the first successful result and caches it.
4. Falls back to a stub response if every provider fails.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from app.cache.history_cache import get_cached_history, store_history
from app.cache.latest_price_cache import get_cached_price, set_cached_price
from app.providers.base import ProviderError
from app.providers.registry import (
    get_daily_history_chain,
    get_latest_price_chain,
    get_provider,
)
from app.schemas.history import DailyBarResponse, HistoryResponse
from app.schemas.quotes import QuoteResponse

logger = logging.getLogger(__name__)


async def get_latest_price(symbol: str, exchange: str | None = None) -> QuoteResponse:
    """Iterate the latest-price provider chain and return the first successful result."""
    symbol = symbol.upper()
    warnings: list[str] = []

    # 1. Cache hit?
    cached = await get_cached_price(symbol)
    if cached is not None:
        logger.debug("Cache hit for %s via %s", symbol, cached.provider)
        return QuoteResponse(
            symbol=symbol,
            exchange=exchange or cached.exchange,
            currency=cached.currency,
            price=cached.price,
            as_of=cached.as_of,
            provider=cached.provider,
            data_status="ok",
            source_type="cache",
            is_realtime=cached.is_realtime,
            is_delayed=cached.is_delayed,
            delay_minutes=cached.delay_minutes,
            confidence="high",
        )

    # 2. Walk the chain
    chain = get_latest_price_chain()
    for name in chain:
        provider = get_provider(name)
        if provider is None or not provider.supports_latest_price():
            continue
        try:
            result = await provider.get_latest_price(symbol)
            # cache the result asynchronously (fire-and-forget style)
            await set_cached_price(result)
            return QuoteResponse(
                symbol=symbol,
                exchange=exchange or result.exchange,
                currency=result.currency,
                price=result.price,
                as_of=result.as_of,
                provider=result.provider,
                data_status="ok",
                source_type="provider",
                is_realtime=result.is_realtime,
                is_delayed=result.is_delayed,
                delay_minutes=result.delay_minutes,
                confidence="high",
            )
        except ProviderError as exc:
            logger.warning("Provider %s failed: %s", name, exc)
            warnings.append(f"{name}: {exc.code}")
        except Exception:
            logger.exception("Unexpected error from provider %s", name)
            warnings.append(f"{name}: INTERNAL_ERROR")

    # 3. Fallback stub
    warnings.append("All providers exhausted. Returning stub data.")
    return QuoteResponse(
        symbol=symbol,
        exchange=exchange,
        currency="USD",
        price=Decimal("0.00"),
        as_of=datetime.now(timezone.utc),
        provider="stub",
        data_status="unavailable",
        source_type="stub",
        is_realtime=False,
        is_delayed=True,
        confidence="low",
        warnings=warnings,
    )


async def get_daily_history(
    symbol: str,
    start_date: date,
    end_date: date,
    timeframe: str = "1d",
) -> HistoryResponse:
    """Iterate the daily-history provider chain and return the best available bars."""
    symbol = symbol.upper()
    warnings: list[str] = []
    providers_used: list[str] = []

    # 1. Check DB cache
    cached_bars = await get_cached_history(symbol, start_date, end_date)
    if cached_bars is not None:
        total_weekdays = sum(
            1 for d in _daterange(start_date, end_date) if d.weekday() < 5
        )
        coverage = len(cached_bars) / max(total_weekdays, 1)
        logger.debug("DB cache hit for %s: %d bars", symbol, len(cached_bars))
        return HistoryResponse(
            symbol=symbol,
            bars=[
                DailyBarResponse(
                    symbol=bar.symbol,
                    date=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    adjusted_close=bar.adjusted_close,
                    volume=bar.volume,
                    currency=bar.currency,
                )
                for bar in cached_bars
            ],
            coverage=round(coverage, 4),
            provider_chain_used=[cached_bars[0].provider] if cached_bars else ["cache"],
            warnings=[],
        )

    # 2. Walk the provider chain
    chain = get_daily_history_chain()
    for name in chain:
        provider = get_provider(name)
        if provider is None or not provider.supports_daily_history():
            continue
        try:
            bars_internal = await provider.get_daily_history(symbol, start_date, end_date)
            if not bars_internal:
                warnings.append(f"{name}: returned 0 bars")
                continue

            # Calculate coverage
            total_weekdays = sum(
                1 for d in _daterange(start_date, end_date) if d.weekday() < 5
            )
            coverage = len(bars_internal) / max(total_weekdays, 1)
            providers_used.append(name)

            # 3. Store in DB cache (fire-and-forget)
            await store_history(symbol, bars_internal, timeframe)

            return HistoryResponse(
                symbol=symbol,
                bars=[
                    DailyBarResponse(
                        symbol=bar.symbol,
                        date=bar.date,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        adjusted_close=bar.adjusted_close,
                        volume=bar.volume,
                        currency=bar.currency,
                    )
                    for bar in bars_internal
                ],
                coverage=round(coverage, 4),
                provider_chain_used=providers_used,
                warnings=warnings if warnings else [],
            )
        except ProviderError as exc:
            logger.warning("Provider %s failed: %s", name, exc)
            warnings.append(f"{name}: {exc.code}")
        except Exception:
            logger.exception("Unexpected error from provider %s", name)
            warnings.append(f"{name}: INTERNAL_ERROR")

    # Fallback stub
    warnings.append("All providers exhausted. Returning empty history.")
    return HistoryResponse(
        symbol=symbol,
        bars=[],
        coverage=0.0,
        provider_chain_used=providers_used or ["stub"],
        warnings=warnings,
    )


def _daterange(start: date, end: date):
    """Yield each date from start to end inclusive."""
    from datetime import timedelta

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
