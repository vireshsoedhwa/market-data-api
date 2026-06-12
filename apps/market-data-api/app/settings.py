from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://stock_user:stock_password@db:5432/stock_dashboard"
    redis_url: str = "redis://redis:6379/0"

    market_data_internal_api_key: str = "change-me-to-a-long-random-token"

    # Provider API keys
    finnhub_api_key: str = ""
    twelvedata_api_key: str = ""
    stockdata_api_key: str = ""
    tiingo_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""
    massive_api_key: str = ""

    # Cache TTLs
    latest_price_ttl_minutes_market_open: int = 5
    latest_price_ttl_minutes_market_closed: int = 60
    daily_history_min_coverage_ratio: float = 0.95

    # Stale policy
    allow_stale_latest_price: bool = True
    max_stale_latest_price_hours: int = 24
    allow_partial_history: bool = True

    # Rate limiting
    rate_limit_requests_per_minute: int = 120
    rate_limit_batch_max_symbols: int = 50

    # API version
    api_version: str = "2.0.0"

    model_config = {"env_file": ".env.marketdata", "extra": "ignore"}


settings = Settings()
