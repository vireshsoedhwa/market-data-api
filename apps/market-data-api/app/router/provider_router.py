"""
Provider router — resolves latest prices and daily history by iterating
through the configured provider chain with fallback logic.

Phase 1: Stub implementation that returns placeholder data.
Real provider adapters will be wired in during Phase 2+.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.schemas.history import DailyBarResponse, HistoryResponse
from app.schemas.quotes import QuoteResponse


async def get_latest_price(symbol: str, exchange: str | None = None) -> QuoteResponse:
    """
    Iterate the latest-price provider chain and return the first successful result.

    TODO: Wire real providers (alpaca, finnhub, …) and cache layer.
    """
    return QuoteResponse(
        symbol=symbol.upper(),
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
        warnings=["No providers configured yet. Returning stub data."],
    )


async def get_daily_history(
    symbol: str,
    start_date: date,
    end_date: date,
    timeframe: str = "1d",
) -> HistoryResponse:
    """
    Iterate the daily-history provider chain and return the best available bars.

    TODO: Wire real providers (tiingo, alpha_vantage, …) and cache layer.
    """
    return HistoryResponse(
        symbol=symbol.upper(),
        bars=[],
        coverage=0.0,
        provider_chain_used=["stub"],
        warnings=["No providers configured yet. Returning empty history."],
    )
