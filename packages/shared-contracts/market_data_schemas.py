from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LatestPriceResponse(BaseModel):
    symbol: str
    exchange: str | None = None
    currency: str | None = None
    price: Decimal
    as_of: datetime
    provider: str
    data_status: str  # fresh | stale
    source_type: str  # provider | daily_close_fallback | cache
    is_realtime: bool = False
    is_delayed: bool = True
    delay_minutes: int | None = None
    confidence: str = "high"  # high | medium | low
    warnings: list[str] = Field(default_factory=list)


class BatchQuoteRequest(BaseModel):
    symbols: list[str]


class BatchQuoteResponse(BaseModel):
    quotes: list[LatestPriceResponse]
    errors: list[dict] = Field(default_factory=list)


class DailyPriceBarResponse(BaseModel):
    symbol: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal
    adjusted_close: Decimal | None = None
    volume: int | None = None
    currency: str | None = None


class DailyHistoryResponse(BaseModel):
    symbol: str
    bars: list[DailyPriceBarResponse]
    coverage: float | None = None
    provider_chain_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RefreshRequest(BaseModel):
    symbols: list[str]
    data_types: list[str] = Field(default_factory=lambda: ["latest_price", "daily_history"])
    start_date: date | None = None
    end_date: date | None = None
    priority: str = "normal"


class RefreshResponse(BaseModel):
    job_id: str
    status: str = "queued"
    symbols_queued: list[str] = Field(default_factory=list)
