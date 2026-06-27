"""
Massive provider — latest price via Single Ticker Snapshot,
daily bars via Custom Bars (OHLC).

Docs: https://massive.com/docs/rest/stocks/overview
Free tier: 5 API requests per minute.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.providers.base import MarketDataProvider, ProviderError
from app.schemas.history import DailyPriceBarInternal
from app.schemas.quotes import LatestPriceInternal
from app.settings import settings

MASSIVE_BASE_URL = "https://api.massive.com"


class MassiveProvider(MarketDataProvider):
    name = "massive"

    def __init__(self) -> None:
        self._api_key = settings.massive_api_key
        self._client = httpx.AsyncClient(
            base_url=MASSIVE_BASE_URL,
            timeout=10.0,
        )

    def supports_latest_price(self) -> bool:
        return True

    def supports_daily_history(self) -> bool:
        return True

    async def get_latest_price(self, symbol: str) -> LatestPriceInternal:
        if not self._api_key:
            raise ProviderError(self.name, "NO_API_KEY", "Massive API key not configured")

        resp = await self._client.get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}",
            params={"apiKey": self._api_key},
        )

        if resp.status_code == 401:
            raise ProviderError(self.name, "AUTH_ERROR", "Invalid Massive API key")
        if resp.status_code == 404:
            raise ProviderError(self.name, "SYMBOL_NOT_FOUND", f"No data for {symbol}")
        if resp.status_code == 429:
            raise ProviderError(self.name, "RATE_LIMITED", "Massive rate limit exceeded")
        if resp.status_code != 200:
            raise ProviderError(self.name, "HTTP_ERROR", f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        ticker = data.get("ticker", {})

        last_trade = ticker.get("lastTrade", {})
        day = ticker.get("day", {})

        # Prefer lastTrade price; fall back to day close
        price = last_trade.get("p") or day.get("c")
        if price is None:
            raise ProviderError(self.name, "NO_DATA", f"No price data in snapshot for {symbol}")

        # lastTrade.t is nanoseconds since epoch
        trade_ts = last_trade.get("t")
        if trade_ts:
            as_of = datetime.fromtimestamp(trade_ts / 1_000_000_000, tz=timezone.utc)
        else:
            as_of = datetime.now(timezone.utc)

        return LatestPriceInternal(
            symbol=symbol.upper(),
            provider=self.name,
            price=Decimal(str(price)),
            currency="USD",
            as_of=as_of,
            is_realtime=True,
            is_delayed=False,
            raw_payload=data,
        )

    async def get_daily_history(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[DailyPriceBarInternal]:
        if not self._api_key:
            raise ProviderError(self.name, "NO_API_KEY", "Massive API key not configured")

        try:
            return await self._fetch_daily_bars(symbol, start_date, end_date)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                self.name, "PARSE_ERROR", f"Failed to fetch/parse history for {symbol}: {exc}"
            ) from exc

    async def _fetch_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[DailyPriceBarInternal]:
        bars: list[DailyPriceBarInternal] = []
        next_url: str | None = None

        while True:
            if next_url:
                resp = await self._client.get(
                    next_url,
                    params={"apiKey": self._api_key},
                )
            else:
                resp = await self._client.get(
                    f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/"
                    f"{start_date.isoformat()}/{end_date.isoformat()}",
                    params={
                        "adjusted": "true",
                        "sort": "asc",
                        "limit": 5000,
                        "apiKey": self._api_key,
                    },
                )

            if resp.status_code == 401:
                raise ProviderError(self.name, "AUTH_ERROR", "Invalid Massive API key")
            if resp.status_code == 429:
                raise ProviderError(self.name, "RATE_LIMITED", "Massive rate limit exceeded")
            if resp.status_code != 200:
                raise ProviderError(
                    self.name, "HTTP_ERROR", f"HTTP {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            for bar in data.get("results", []) or []:
                # bar.t is milliseconds since epoch
                bar_date = datetime.fromtimestamp(
                    bar["t"] / 1000, tz=timezone.utc
                ).date()
                bars.append(
                    DailyPriceBarInternal(
                        symbol=symbol.upper(),
                        provider=self.name,
                        date=bar_date,
                        open=Decimal(str(bar["o"])),
                        high=Decimal(str(bar["h"])),
                        low=Decimal(str(bar["l"])),
                        close=Decimal(str(bar["c"])),
                        volume=bar.get("v"),
                        currency="USD",
                        raw_payload=bar,
                    )
                )

            next_url = data.get("next_url")
            if not next_url:
                break

        return bars
