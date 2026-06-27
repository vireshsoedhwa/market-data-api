"""
History cache — TimescaleDB-backed cache for daily price bars.

Reads from / writes to market_data.price_bars.
On cache hit (coverage >= threshold), returns bars from DB without hitting providers.
On cache miss, the caller fetches from providers and stores the result here.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.schemas.history import DailyPriceBarInternal
from app.settings import settings

logger = logging.getLogger(__name__)


def _count_weekdays(start_date: date, end_date: date) -> int:
    """Count weekdays (Mon-Fri) in [start_date, end_date] inclusive."""
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


async def get_cached_history(
    symbol: str, start_date: date, end_date: date
) -> list[DailyPriceBarInternal] | None:
    """
    Return cached bars from the DB if coverage meets the threshold.
    Returns None on cache miss (insufficient coverage).
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT
                        symbol, ts::date AS bar_date,
                        open, high, low, close, adjusted_close, volume, source
                    FROM market_data.price_bars
                    WHERE symbol = :symbol
                      AND timeframe = '1d'
                      AND ts >= :start_date
                      AND ts < :end_date_exclusive
                    ORDER BY ts ASC
                """),
                {
                    "symbol": symbol.upper(),
                    "start_date": start_date.isoformat(),
                    "end_date_exclusive": (end_date + timedelta(days=1)).isoformat(),
                },
            )
            rows = result.fetchall()

        if not rows:
            return None

        total_weekdays = _count_weekdays(start_date, end_date)
        coverage = len(rows) / max(total_weekdays, 1)

        if coverage < settings.daily_history_min_coverage_ratio:
            logger.debug(
                "Cache miss for %s: coverage %.2f < threshold %.2f",
                symbol, coverage, settings.daily_history_min_coverage_ratio,
            )
            return None

        bars = [
            DailyPriceBarInternal(
                symbol=row.symbol,
                provider=row.source,
                date=row.bar_date,
                open=Decimal(str(row.open)) if row.open is not None else None,
                high=Decimal(str(row.high)) if row.high is not None else None,
                low=Decimal(str(row.low)) if row.low is not None else None,
                close=Decimal(str(row.close)),
                adjusted_close=Decimal(str(row.adjusted_close)) if row.adjusted_close is not None else None,
                volume=row.volume,
                currency="USD",
            )
            for row in rows
        ]

        logger.debug("Cache hit for %s: %d bars, coverage %.2f", symbol, len(bars), coverage)
        return bars

    except Exception:
        logger.warning("History cache read error for %s", symbol, exc_info=True)
        return None


async def store_history(
    symbol: str, bars: list[DailyPriceBarInternal], timeframe: str = "1d"
) -> None:
    """
    Upsert bars into market_data.price_bars.
    Uses ON CONFLICT to avoid duplicates.
    """
    if not bars:
        return

    try:
        async with async_session_factory() as session:
            for bar in bars:
                await session.execute(
                    text("""
                        INSERT INTO market_data.price_bars
                            (symbol, timeframe, ts, open, high, low, close, adjusted_close, volume, source)
                        VALUES
                            (:symbol, :timeframe, :ts, :open, :high, :low, :close, :adjusted_close, :volume, :source)
                        ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            adjusted_close = EXCLUDED.adjusted_close,
                            volume = EXCLUDED.volume,
                            source = EXCLUDED.source
                    """),
                    {
                        "symbol": bar.symbol.upper(),
                        "timeframe": timeframe,
                        "ts": bar.date.isoformat(),
                        "open": str(bar.open) if bar.open is not None else None,
                        "high": str(bar.high) if bar.high is not None else None,
                        "low": str(bar.low) if bar.low is not None else None,
                        "close": str(bar.close),
                        "adjusted_close": str(bar.adjusted_close) if bar.adjusted_close is not None else None,
                        "volume": bar.volume,
                        "source": bar.provider,
                    },
                )
            await session.commit()

        logger.debug("Stored %d bars for %s in cache", len(bars), symbol)

    except Exception:
        logger.warning("History cache write error for %s", symbol, exc_info=True)
