"""
Tiingo provider — daily historical bars via the Tiingo REST API.

Docs: https://www.tiingo.com/documentation/end-of-day
Free tier: 1,000 requests/day, 50 requests/hour.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.providers.base import MarketDataProvider, ProviderError
from app.schemas.history import DailyPriceBarInternal
from app.schemas.quotes import LatestPriceInternal
from app.settings import settings

TIINGO_BASE_URL = "https://api.tiingo.com"


class TiingoProvider(MarketDataProvider):
    name = "tiingo"

    def __init__(self) -> None:
        self._api_key = settings.tiingo_api_key
        self._client = httpx.AsyncClient(
            base_url=TIINGO_BASE_URL,
            timeout=15.0,
            headers={"Content-Type": "application/json"},
        )

    def supports_latest_price(self) -> bool:
        return False

    def supports_daily_history(self) -> bool:
        return True

    async def get_latest_price(self, symbol: str) -> LatestPriceInternal:
        raise ProviderError(self.name, "NOT_SUPPORTED", "Tiingo does not support latest price via this adapter")

    async def get_daily_history(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[DailyPriceBarInternal]:
        if not self._api_key:
            raise ProviderError(self.name, "NO_API_KEY", "Tiingo API key not configured")

        resp = await self._client.get(
            f"/tiingo/daily/{symbol.lower()}/prices",
            params={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "token": self._api_key,
            },
        )

        if resp.status_code == 401:
            raise ProviderError(self.name, "AUTH_ERROR", "Invalid Tiingo API key")
        if resp.status_code == 404:
            raise ProviderError(self.name, "SYMBOL_NOT_FOUND", f"No data for {symbol}")
        if resp.status_code == 429:
            raise ProviderError(self.name, "RATE_LIMITED", "Tiingo rate limit exceeded")
        if resp.status_code != 200:
            raise ProviderError(self.name, "HTTP_ERROR", f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        if not isinstance(data, list):
            raise ProviderError(self.name, "PARSE_ERROR", f"Unexpected response format for {symbol}")

        bars: list[DailyPriceBarInternal] = []
        for item in data:
            bar_date = datetime.fromisoformat(item["date"]).date()
            bars.append(
                DailyPriceBarInternal(
                    symbol=symbol.upper(),
                    provider=self.name,
                    date=bar_date,
                    open=Decimal(str(item["open"])) if item.get("open") is not None else None,
                    high=Decimal(str(item["high"])) if item.get("high") is not None else None,
                    low=Decimal(str(item["low"])) if item.get("low") is not None else None,
                    close=Decimal(str(item["close"])),
                    adjusted_close=Decimal(str(item["adjClose"])) if item.get("adjClose") is not None else None,
                    volume=item.get("volume"),
                    currency="USD",
                    raw_payload=item,
                )
            )

        return bars
