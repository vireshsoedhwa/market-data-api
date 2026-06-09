"""
Latest price cache — Redis-backed cache for latest-price quotes.

Keys:   quote:{SYMBOL}
Values: JSON-serialized LatestPriceInternal
TTL:    Configurable per market-open/closed status.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

import redis.asyncio as aioredis

from app.schemas.quotes import LatestPriceInternal
from app.settings import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _cache_key(symbol: str) -> str:
    return f"quote:{symbol.upper()}"


def _ttl_seconds() -> int:
    """Use shorter TTL during US market hours (rough heuristic)."""
    now = datetime.now(timezone.utc)
    hour_utc = now.hour
    # NYSE open ~13:30-20:00 UTC
    if 13 <= hour_utc < 21 and now.weekday() < 5:
        return settings.latest_price_ttl_minutes_market_open * 60
    return settings.latest_price_ttl_minutes_market_closed * 60


async def get_cached_price(symbol: str) -> LatestPriceInternal | None:
    """Return cached price or None if miss/expired."""
    try:
        r = _get_redis()
        raw = await r.get(_cache_key(symbol))
        if raw is None:
            return None
        data = json.loads(raw)
        return LatestPriceInternal(**data)
    except Exception:
        logger.warning("Cache read error for %s", symbol, exc_info=True)
        return None


async def set_cached_price(result: LatestPriceInternal) -> None:
    """Write a price to cache with market-aware TTL."""
    try:
        r = _get_redis()
        payload = result.model_dump(mode="json")
        # Decimal → str for JSON serialization
        payload["price"] = str(payload["price"])
        await r.set(_cache_key(result.symbol), json.dumps(payload), ex=_ttl_seconds())
    except Exception:
        logger.warning("Cache write error for %s", result.symbol, exc_info=True)
