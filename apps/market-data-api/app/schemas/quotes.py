from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LatestPriceInternal(BaseModel):
    """Internal normalized model returned by providers."""

    symbol: str
    provider: str
    price: Decimal
    currency: str | None = None
    as_of: datetime
    exchange: str | None = None
    is_realtime: bool = False
    is_delayed: bool = True
    delay_minutes: int | None = None
    raw_payload: dict | None = None


class QuoteResponse(BaseModel):
    symbol: str
    exchange: str | None = None
    currency: str | None = None
    price: Decimal
    as_of: datetime
    provider: str
    data_status: str
    source_type: str
    is_realtime: bool = False
    is_delayed: bool = True
    delay_minutes: int | None = None
    confidence: str = "high"
    warnings: list[str] = Field(default_factory=list)


class BatchQuoteRequest(BaseModel):
    symbols: list[str]


class BatchQuoteResponse(BaseModel):
    quotes: list[QuoteResponse]
    errors: list[dict] = Field(default_factory=list)
