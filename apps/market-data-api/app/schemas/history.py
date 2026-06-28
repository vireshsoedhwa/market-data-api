from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class DailyPriceBarInternal(BaseModel):
    """Internal normalized model returned by providers."""

    symbol: str
    provider: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal
    adjusted_close: Decimal | None = None
    volume: int | None = None
    currency: str | None = None
    raw_payload: dict | None = None


class DailyBarResponse(BaseModel):
    symbol: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal
    adjusted_close: Decimal | None = None
    volume: int | None = None
    currency: str | None = None


class HistoryResponse(BaseModel):
    symbol: str
    bars: list[DailyBarResponse]
    coverage: float | None = None
    provider_chain_used: list[str] = Field(default_factory=list)
    source_type: str = "provider"  # "cache" or "provider"
    warnings: list[str] = Field(default_factory=list)


class BatchHistoryRequest(BaseModel):
    symbols: list[str]
    start_date: date
    end_date: date
    timeframe: str = "1d"
