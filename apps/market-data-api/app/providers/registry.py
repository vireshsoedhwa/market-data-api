"""
Provider registry — loads providers.yml and builds ordered chains.

Returns concrete MarketDataProvider instances keyed by name,
plus the ordered chain lists for latest-price and daily-history.
"""

import logging
from pathlib import Path

import yaml

from app.providers.base import MarketDataProvider
from app.providers.finnhub import FinnhubProvider
from app.providers.massive import MassiveProvider

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "providers.yml"

# Map provider name → class. Extend as new adapters are added.
_PROVIDER_CLASSES: dict[str, type[MarketDataProvider]] = {
    "finnhub": FinnhubProvider,
    "massive": MassiveProvider,
}

# Singleton instances
_instances: dict[str, MarketDataProvider] = {}
_latest_price_chain: list[str] = []
_daily_history_chain: list[str] = []
_loaded = False


def _load() -> None:
    global _loaded
    if _loaded:
        return

    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}

    market_data = cfg.get("market_data", {})
    raw_price_chain = market_data.get("latest_price_chain", [])
    raw_history_chain = market_data.get("daily_history_chain", [])

    for name in set(raw_price_chain + raw_history_chain):
        if name in _PROVIDER_CLASSES:
            try:
                _instances[name] = _PROVIDER_CLASSES[name]()
                logger.info("Loaded provider: %s", name)
            except Exception:
                logger.exception("Failed to load provider: %s", name)
        else:
            logger.debug("Skipping unknown provider in chain: %s", name)

    _latest_price_chain.extend(raw_price_chain)
    _daily_history_chain.extend(raw_history_chain)
    _loaded = True


def get_provider(name: str) -> MarketDataProvider | None:
    _load()
    return _instances.get(name)


def get_latest_price_chain() -> list[str]:
    _load()
    return list(_latest_price_chain)


def get_daily_history_chain() -> list[str]:
    _load()
    return list(_daily_history_chain)


def get_all_providers() -> dict[str, MarketDataProvider]:
    _load()
    return dict(_instances)
