from abc import ABC, abstractmethod
from datetime import date

from app.schemas.history import DailyPriceBarInternal
from app.schemas.quotes import LatestPriceInternal


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def supports_latest_price(self) -> bool:
        ...

    @abstractmethod
    def supports_daily_history(self) -> bool:
        ...

    @abstractmethod
    async def get_latest_price(self, symbol: str) -> LatestPriceInternal:
        ...

    @abstractmethod
    async def get_daily_history(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[DailyPriceBarInternal]:
        ...


class ProviderError(Exception):
    def __init__(self, provider: str, code: str, message: str):
        self.provider = provider
        self.code = code
        self.message = message
        super().__init__(f"[{provider}] {code}: {message}")
