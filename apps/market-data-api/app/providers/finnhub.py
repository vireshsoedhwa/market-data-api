"""
Finnhub provider — latest stock quotes via the /quote endpoint.

Docs: https://finnhub.io/docs/api/quote
Free tier: 60 calls/min.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.providers.base import MarketDataProvider, ProviderError
from app.schemas.history import DailyPriceBarInternal
from app.schemas.quotes import LatestPriceInternal
from app.settings import settings

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubProvider(MarketDataProvider):
    name = "finnhub"

    def __init__(self) -> None:
        self._api_key = settings.finnhub_api_key
        self._client = httpx.AsyncClient(
            base_url=FINNHUB_BASE_URL,
            timeout=10.0,
        )

    def supports_latest_price(self) -> bool:
        return True

    def supports_daily_history(self) -> bool:
        return False

    async def get_latest_price(self, symbol: str) -> LatestPriceInternal:
        if not self._api_key:
            raise ProviderError(self.name, "NO_API_KEY", "Finnhub API key not configured")

        resp = await self._client.get(
            "/quote",
            params={"symbol": symbol.upper(), "token": self._api_key},
        )

        if resp.status_code == 429:
            raise ProviderError(self.name, "RATE_LIMITED", "Finnhub rate limit exceeded")
        if resp.status_code != 200:
            raise ProviderError(self.name, "HTTP_ERROR", f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()

        # Finnhub returns c=0 for unknown symbols
        if data.get("c", 0) == 0 and data.get("t", 0) == 0:
            raise ProviderError(self.name, "SYMBOL_NOT_FOUND", f"No data for {symbol}")

        return LatestPriceInternal(
            symbol=symbol.upper(),
            provider=self.name,
            price=Decimal(str(data["c"])),
            currency="USD",
            as_of=datetime.fromtimestamp(data["t"], tz=timezone.utc) if data.get("t") else datetime.now(timezone.utc),
            is_realtime=False,
            is_delayed=True,
            delay_minutes=15,
            raw_payload=data,
        )

    async def get_daily_history(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[DailyPriceBarInternal]:
        raise ProviderError(self.name, "NOT_SUPPORTED", "Finnhub does not support daily history")
