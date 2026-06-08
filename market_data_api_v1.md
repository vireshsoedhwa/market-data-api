# Market Data API — Plan v1

## 1. Service Goal

A standalone, independently deployable API responsible for all external market data acquisition, normalization, caching, and provider management.

This is the **only** service that knows how each external data provider works. The Portfolio API calls this service over HTTP with symbol lists — it never calls providers directly.

---

## 2. Technology Stack

```text
Framework:          Python FastAPI (port 8010)
Database:           PostgreSQL + TimescaleDB (market_data schema)
Background jobs:    Celery (market-data-worker)
Queue/cache:        Redis
ORM/migrations:    SQLAlchemy + Alembic
HTTP client:        httpx
Containerization:   Docker Compose
```

---

## 3. High-Level Architecture

```text
Portfolio API (consumer)
   │
   │ HTTP calls (internal)
   ▼
Market Data API (port 8010)
- latest prices
- historical bars
- provider routing & fallback
- rate limits, cache
- provider health
   │
   ├── Redis (rate limits, queues)
   ├── TimescaleDB / market_data schema
   └── Market Data Worker (Celery)
        ├── Alpaca
        ├── Finnhub
        ├── Twelve Data
        ├── StockData.org
        ├── Tiingo
        ├── Alpha Vantage
        ├── FMP
        └── Stooq
```

The key principle:

```text
Portfolio API asks: "What market data do I need?" (passes symbols)
Market Data API answers: "Here is the best available normalized market data."
```

---

## 4. Service Responsibilities

The Market Data API owns:

```text
provider adapters (Alpaca, Finnhub, Tiingo, Alpha Vantage, FMP, Stooq, etc.)
provider router + fallback chain
provider_symbol_mappings
latest_price_cache
price_bars
quote_snapshots
api_cache_entries
market_data_fetch_jobs
market_data_providers
market_data_provider_credentials
provider_rate_limit_rules
provider_request_log
provider_health_state
normalizers
freshness policy / staleness policy
circuit breaker
```

---

## 5. Main Design Rule

The Market Data API must **not** know about portfolios or watchlists.

Avoid endpoints like:

```http
POST /refresh-portfolio/{portfolio_id}
POST /refresh-watchlist/{watchlist_id}
GET  /portfolio-prices/{portfolio_id}
```

Those create coupling between services.

The Market Data API accepts **symbols**, not portfolio IDs.

---

## 6. Symbol Identity at the API Boundary

Use symbols and basic market identity fields — not internal database UUIDs.

US stock:

```json
{"symbol": "NVDA", "exchange": "NASDAQ", "currency": "USD", "asset_type": "stock"}
```

Canadian stock:

```json
{"symbol": "SHOP", "exchange": "TSX", "currency": "CAD", "asset_type": "stock", "country": "CA"}
```

The Market Data API internally translates symbols into provider-specific formats via `provider_symbol_mappings`:

```text
SHOP on TSX → Alpha Vantage: SHOP.TRT, Yahoo: SHOP.TO
```

---

## 7. API Endpoints

```http
GET  /health
GET  /v1/providers/status

GET  /v1/quotes/{symbol}
POST /v1/quotes/batch

GET  /v1/history/{symbol}?start_date=...&end_date=...&timeframe=1d
POST /v1/history/batch

POST /v1/refresh
GET  /v1/jobs/{job_id}

GET  /v1/symbols/search?query=nvda
GET  /v1/symbols/{symbol}/metadata
```

### 7.1 Latest Quote Response

```json
{
  "symbol": "NVDA",
  "exchange": "NASDAQ",
  "currency": "USD",
  "price": "123.45",
  "as_of": "2026-06-04T20:45:00Z",
  "provider": "alpaca",
  "data_status": "fresh",
  "source_type": "provider",
  "is_realtime": false,
  "is_delayed": true,
  "delay_minutes": 15,
  "confidence": "high",
  "warnings": []
}
```

### 7.2 Fallback Response

```json
{
  "symbol": "NVDA",
  "price": "122.91",
  "as_of": "2026-06-03T21:00:00Z",
  "provider": "daily_close_fallback",
  "data_status": "stale",
  "source_type": "daily_close_fallback",
  "is_realtime": false,
  "is_delayed": true,
  "confidence": "medium",
  "warnings": ["Live quote providers unavailable. Using latest daily close."]
}
```

### 7.3 Refresh Endpoint

```http
POST /v1/refresh
```

```json
{
  "symbols": ["NVDA", "AAPL", "IONQ", "QBTS"],
  "data_types": ["latest_price", "daily_history"],
  "start_date": "2024-01-01",
  "end_date": "2026-06-04",
  "priority": "normal"
}
```

Response:

```json
{
  "job_id": "refresh_123",
  "status": "queued",
  "symbols_queued": ["NVDA", "AAPL", "IONQ", "QBTS"]
}
```

---

## 8. Multi-Provider Layer

### 8.1 Latest Price Provider Chain

```text
get_latest_price(symbol):
    1. Check latest_price_cache
    2. If cache fresh → return cached price
    3. Try Alpaca
    4. Try Finnhub
    5. Try Twelve Data
    6. Try StockData.org
    7. Fall back to latest daily close from price_bars
```

| Priority | Provider | Reason |
|---:|---|---|
| 1 | Local quote cache | Fastest, no API call |
| 2 | Alpaca | Best free option for current US stock prices |
| 3 | Finnhub | Good backup for latest quotes |
| 4 | Twelve Data | Good secondary backup |
| 5 | StockData.org | Light-use fallback |
| 6 | Latest daily close | Final fallback when all live providers fail |

### 8.2 Daily Historical Price Provider Chain

```text
get_daily_history(symbol, start_date, end_date):
    1. Check TimescaleDB price_bars
    2. If coverage >= 95% → return local data
    3. Try Tiingo
    4. Try Alpha Vantage
    5. Try FMP (Financial Modeling Prep)
    6. Try Twelve Data
    7. Try Stooq backfill
```

| Priority | Provider | Reason |
|---:|---|---|
| 1 | TimescaleDB price_bars | Fastest, no API call |
| 2 | Tiingo | Good historical EOD provider |
| 3 | Alpha Vantage | Good for daily adjusted data |
| 4 | FMP | Useful backup for EOD |
| 5 | Twelve Data | Backup time-series provider |
| 6 | Stooq | Useful offline/backfill source |

### 8.3 Provider Interface

```python
from abc import ABC, abstractmethod
from datetime import date


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def supports_latest_price(self) -> bool:
        pass

    @abstractmethod
    def supports_daily_history(self) -> bool:
        pass

    @abstractmethod
    async def get_latest_price(self, symbol: str):
        pass

    @abstractmethod
    async def get_daily_history(self, symbol: str, start_date: date, end_date: date):
        pass
```

### 8.4 Normalized Internal Models

**LatestPrice:**

```python
class LatestPrice(BaseModel):
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
```

**DailyPriceBar:**

```python
class DailyPriceBar(BaseModel):
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
```

**ProviderResult:**

```python
class ProviderResult(BaseModel):
    success: bool
    provider: str
    data: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    used_cache: bool = False
    is_stale: bool = False
```

---

## 9. Provider Configuration

Provider chain order and cache settings live in a **YAML config file only** (requires app restart to change). Database tables are used only for runtime state (health, request logs, rate limit tracking).

```yaml
market_data:
  latest_price_chain:
    - alpaca
    - finnhub
    - twelvedata
    - stockdata
    - daily_close_fallback

  daily_history_chain:
    - tiingo
    - alpha_vantage
    - fmp
    - twelvedata
    - stooq

  cache:
    latest_price_ttl_minutes_market_open: 5
    latest_price_ttl_minutes_market_closed: 60
    daily_history_min_coverage_ratio: 0.95

  stale_policy:
    allow_stale_latest_price: true
    max_stale_latest_price_hours: 24
    allow_partial_history: true
```

---

## 10. Cache Strategy

### 10.1 Durable Cache (PostgreSQL/TimescaleDB — market_data schema)

- Historical price bars (never expire, append/update).
- Raw API responses (`api_cache_entries`).
- Fetch job logs.

### 10.2 Short-Lived Cache (Redis)

- Latest quote responses.
- Rate limit counters.
- Background job queues (Celery broker).

### 10.3 Cache TTLs

```text
Latest price (market open):     5 minutes
Latest price (market closed):   60 minutes
Latest price (weekend/holiday): Use last available close
Daily price bars:               Permanent (refresh last 5-10 days for adjustments)
Symbol search results:          7 days
```

### 10.4 Staleness Policy

```yaml
allow_stale_latest_price: true
max_stale_latest_price_hours: 24
allow_partial_history: true
daily_history_min_coverage_ratio: 0.95
```

---

## 11. Rate Limiting & Provider Health

### 11.1 Per-Provider Rate Limiting

Each provider has configurable rate limit rules (requests per minute, per day, per endpoint). If a provider is rate-limited, the router skips it and tries the next.

### 11.2 Circuit Breaker

```text
3 consecutive failures → mark provider as degraded
5 consecutive failures → disable provider for 15 minutes
Rate-limit error       → disable until window resets
```

### 11.3 Provider Health Tracking

Track per-provider: status (healthy/degraded/rate_limited/disabled/failing), last success/failure timestamps, consecutive failure count, average latency.

---

## 12. Data Quality Flags

Every market data response includes quality metadata:

```json
{
  "symbol": "NVDA",
  "price": "123.45",
  "provider": "alpaca",
  "as_of": "2026-06-04T20:45:00Z",
  "data_status": "fresh",
  "is_stale": false,
  "confidence": "high",
  "warnings": []
}
```

When using fallback data:

```json
{
  "data_status": "stale",
  "warning": "Live quote providers unavailable. Using latest daily close."
}
```

---

## 13. Error Handling

Standardized error codes:

```text
PROVIDER_RATE_LIMITED
PROVIDER_TIMEOUT
PROVIDER_AUTH_FAILED
PROVIDER_BAD_SYMBOL
PROVIDER_EMPTY_RESPONSE
PROVIDER_UNSUPPORTED_ENDPOINT
PROVIDER_DATA_STALE
MARKET_DATA_UNAVAILABLE
```

The Portfolio API (and frontend) does not see individual provider failures — only aggregated `data_status` and `warnings`.

---

## 14. Background Jobs (Market Data Worker)

### 14.1 Responsibilities

```text
fetch latest quotes
fetch daily bars
refresh stale data
backfill history
provider health checks
rate-limit-aware provider jobs
```

### 14.2 Schedules

**Daily after market close:**
- Refresh daily bars for known symbols.

**During market hours:**
- Refresh latest prices every 5-15 minutes.

**Weekly:**
- Refresh fundamentals, ETF profiles, provider metadata.

---

## 15. Authentication

For local development, use a static internal API token:

```text
MARKET_DATA_INTERNAL_API_KEY=some-long-random-token
```

The Portfolio API sends:

```http
Authorization: Bearer <token>
```

The Market Data API validates it.

Later this can be replaced with OAuth, mTLS, or service mesh auth.

---

## 16. Database Schema (market_data)

### 16.1 Provider Symbol Mappings

```sql
CREATE SCHEMA IF NOT EXISTS market_data;

CREATE TABLE market_data.provider_symbol_mappings (
    id UUID PRIMARY KEY,
    symbol TEXT NOT NULL,
    exchange TEXT,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(symbol, exchange, provider)
);
```

### 16.2 Price Bars

```sql
CREATE TABLE market_data.price_bars (
    symbol TEXT NOT NULL,
    exchange TEXT,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,

    open NUMERIC(24, 8),
    high NUMERIC(24, 8),
    low NUMERIC(24, 8),
    close NUMERIC(24, 8),
    adjusted_close NUMERIC(24, 8),
    volume BIGINT,

    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (symbol, timeframe, ts)
);

SELECT create_hypertable('market_data.price_bars', 'ts');
```

Timeframe values (start with `1d` only): `1d`, `1h`, `15m`, `5m`, `1m`

### 16.3 Quote Snapshots

```sql
CREATE TABLE market_data.quote_snapshots (
    symbol TEXT NOT NULL,
    exchange TEXT,
    ts TIMESTAMPTZ NOT NULL,

    price NUMERIC(24, 8),
    open NUMERIC(24, 8),
    high NUMERIC(24, 8),
    low NUMERIC(24, 8),
    previous_close NUMERIC(24, 8),
    volume BIGINT,

    source TEXT NOT NULL,
    raw_payload JSONB,

    PRIMARY KEY (symbol, ts)
);

CREATE VIEW market_data.latest_quotes AS
SELECT DISTINCT ON (symbol)
    symbol,
    exchange,
    ts,
    price,
    open,
    high,
    low,
    previous_close,
    volume
FROM market_data.quote_snapshots
ORDER BY symbol, ts DESC;
```

### 16.4 Latest Price Cache

```sql
CREATE TABLE market_data.latest_price_cache (
    symbol TEXT NOT NULL,
    exchange TEXT,

    provider TEXT NOT NULL,
    price NUMERIC(24, 8) NOT NULL,
    currency TEXT,
    as_of TIMESTAMPTZ NOT NULL,

    is_realtime BOOLEAN NOT NULL DEFAULT false,
    is_delayed BOOLEAN NOT NULL DEFAULT true,
    delay_minutes INTEGER,

    expires_at TIMESTAMPTZ NOT NULL,
    raw_payload JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (symbol, exchange)
);
```

### 16.5 API Cache Entries

```sql
CREATE TABLE market_data.api_cache_entries (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_hash TEXT NOT NULL UNIQUE,
    request_params JSONB NOT NULL,
    response_payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    status_code INTEGER,
    error_message TEXT
);
```

### 16.6 Market Data Fetch Jobs

```sql
CREATE TABLE market_data.market_data_fetch_jobs (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    symbol TEXT,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    raw_response JSONB
);
```

Status values: `queued`, `running`, `success`, `failed`, `rate_limited`, `skipped_cache_valid`

### 16.7 Market Data Providers

```sql
CREATE TABLE market_data.market_data_providers (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT true,

    supports_latest_price BOOLEAN NOT NULL DEFAULT false,
    supports_daily_history BOOLEAN NOT NULL DEFAULT false,
    supports_fundamentals BOOLEAN NOT NULL DEFAULT false,

    base_url TEXT,
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 16.8 Provider Credentials

```sql
CREATE TABLE market_data.market_data_provider_credentials (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data.market_data_providers(id),

    credential_name TEXT NOT NULL,
    env_var_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(provider_id, credential_name)
);
```

### 16.9 Provider Rate Limit Rules

```sql
CREATE TABLE market_data.provider_rate_limit_rules (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data.market_data_providers(id),

    rule_name TEXT NOT NULL,
    max_requests INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,

    applies_to_endpoint TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example values: `alpaca: 200/60s`, `finnhub: 60/60s`

### 16.10 Provider Request Log

```sql
CREATE TABLE market_data.provider_request_log (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data.market_data_providers(id),

    endpoint TEXT NOT NULL,
    symbol TEXT,
    request_params JSONB,

    status TEXT NOT NULL,
    http_status_code INTEGER,
    error_code TEXT,
    error_message TEXT,

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    used_cache BOOLEAN NOT NULL DEFAULT false
);
```

Status values: `success`, `failed`, `rate_limited`, `timeout`, `provider_disabled`, `cache_hit`

### 16.11 Provider Health State

```sql
CREATE TABLE market_data.provider_health_state (
    provider_id UUID PRIMARY KEY REFERENCES market_data.market_data_providers(id),

    status TEXT NOT NULL,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    disabled_until TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Status values: `healthy`, `degraded`, `rate_limited`, `disabled`, `failing`

---

## 17. Environment Variables (.env.marketdata)

```bash
DATABASE_URL=postgresql+asyncpg://stock_user:stock_password@db:5432/stock_dashboard
REDIS_URL=redis://redis:6379/0

MARKET_DATA_INTERNAL_API_KEY=change-me

ALPACA_API_KEY=
ALPACA_API_SECRET=
FINNHUB_API_KEY=
TWELVEDATA_API_KEY=
STOCKDATA_API_KEY=
TIINGO_API_KEY=
ALPHA_VANTAGE_API_KEY=
FMP_API_KEY=
```

Provider API keys live **only** in `.env.marketdata`. The Portfolio API has no access to them.

---

## 18. Project Structure

```text
apps/
├── market-data-api/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── quotes.py
│   │   │   ├── history.py
│   │   │   ├── refresh.py
│   │   │   ├── symbols.py
│   │   │   └── providers.py
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── alpaca.py
│   │   │   ├── finnhub.py
│   │   │   ├── twelvedata.py
│   │   │   ├── stockdata.py
│   │   │   ├── tiingo.py
│   │   │   ├── alpha_vantage.py
│   │   │   ├── fmp.py
│   │   │   └── stooq.py
│   │   ├── router/
│   │   │   └── provider_router.py
│   │   ├── cache/
│   │   │   ├── latest_price_cache.py
│   │   │   └── history_cache.py
│   │   ├── normalizers/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   └── settings.py
│   ├── Dockerfile
│   └── requirements.txt
│
└── market-data-worker/
    ├── app/
    │   ├── celery_app.py
    │   └── tasks.py
    └── Dockerfile
```

---

## 19. Docker Compose (Market Data services)

```yaml
services:
  market-data-api:
    build: ./apps/market-data-api
    ports:
      - "8010:8010"
    env_file:
      - .env.marketdata
    depends_on:
      - db
      - redis

  market-data-worker:
    build: ./apps/market-data-worker
    env_file:
      - .env.marketdata
    depends_on:
      - db
      - redis

  db:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: stock_dashboard
      POSTGRES_USER: stock_user
      POSTGRES_PASSWORD: stock_password
    ports:
      - "5432:5432"
    volumes:
      - stock_db_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  stock_db_data:
```

---

## 20. Implementation Roadmap

### Phase 1: Standalone Market Data API MVP

- Market Data API service (separate FastAPI app, port 8010).
- Market Data Worker (Celery).
- Latest quote endpoint: `GET /v1/quotes/{symbol}`
- Daily history endpoint: `GET /v1/history/{symbol}`
- Alpha Vantage daily history provider.
- Alpaca latest quote provider.
- `latest_price_cache` and `price_bars` tables (market_data schema).
- `provider_symbol_mappings` table.
- Internal API key auth.

**Goal:** `GET /v1/quotes/NVDA` and `GET /v1/history/NVDA` work independently.

### Phase 2: Add Provider Health and Fallback

- Provider request log.
- Provider health state.
- Rate limiter.
- Circuit breaker.
- Full fallback provider chain.

**Goal:** System remains usable when one provider is down or rate-limited.

### Phase 3: Add Remaining Providers

- Finnhub, Twelve Data, StockData.org, Tiingo, FMP, Stooq.

**Goal:** Market Data API becomes resilient through multiple providers.

---

## 21. Shared Contracts

A small shared package for request/response models used by both services:

```text
packages/shared-contracts/
├── market_data_schemas.py
└── errors.py
```

Contains:

```text
Pydantic schemas (LatestPriceResponse, DailyHistoryResponse, etc.)
Shared error codes
Shared enums
```

Example shared model:

```python
class LatestPriceResponse(BaseModel):
    symbol: str
    exchange: str | None = None
    currency: str | None = None
    price: Decimal
    as_of: datetime
    provider: str
    data_status: str
    source_type: str
    is_realtime: bool
    is_delayed: bool
    delay_minutes: int | None = None
    confidence: str
    warnings: list[str] = []
```

---

## Appendix A: Key Pseudocode

### A.1 get_latest_price

```python
async def get_latest_price(symbol: str) -> LatestPriceResponse:
    cached = await latest_price_cache_repo.get(symbol)

    if cached and cached.expires_at > now():
        return cached.to_response()

    provider_chain = config.latest_price_chain  # from YAML

    errors = []

    for provider_name in provider_chain:
        provider = provider_registry.get(provider_name)

        if not provider.supports_latest_price():
            continue

        if await rate_limiter.is_limited(provider_name):
            errors.append(f"{provider_name}: rate limited")
            continue

        if await provider_health.is_disabled(provider_name):
            errors.append(f"{provider_name}: disabled")
            continue

        try:
            resolved_symbol = await symbol_mapper.resolve(symbol, provider_name)
            latest_price = await provider.get_latest_price(resolved_symbol)

            await latest_price_cache_repo.upsert(
                symbol=symbol,
                latest_price=latest_price,
                ttl_minutes=get_latest_price_ttl()
            )

            await quote_snapshot_repo.insert(symbol=symbol, latest_price=latest_price)

            return latest_price.to_response()

        except ProviderError as error:
            errors.append(f"{provider_name}: {error}")
            await provider_health.record_failure(provider_name, error)

    # Final fallback: latest daily close
    fallback = await price_bar_repo.get_latest_daily_close(symbol)

    if fallback:
        return LatestPriceResponse(
            symbol=symbol,
            provider="daily_close_fallback",
            price=fallback.adjusted_close or fallback.close,
            as_of=fallback.ts,
            data_status="stale",
            source_type="daily_close_fallback",
            is_realtime=False,
            is_delayed=True,
            confidence="medium",
            warnings=["Live quote providers unavailable. Using latest daily close."]
        )

    raise MarketDataUnavailableError(
        symbol=symbol,
        message="No latest price available from cache, providers, or daily close fallback."
    )
```

### A.2 get_daily_history

```python
async def get_daily_history(
    symbol: str,
    start_date: date,
    end_date: date
) -> DailyHistoryResponse:

    local_bars = await price_bar_repo.get_daily_bars(
        symbol=symbol, start_date=start_date, end_date=end_date
    )

    coverage = calculate_history_coverage(local_bars, start_date, end_date)

    if coverage >= settings.daily_history_min_coverage_ratio:
        return DailyHistoryResponse(
            symbol=symbol, bars=local_bars, coverage=coverage,
            provider_chain_used=["local_cache"]
        )

    missing_ranges = calculate_missing_ranges(local_bars, start_date, end_date)

    provider_chain = config.daily_history_chain  # from YAML
    errors = []

    for provider_name in provider_chain:
        provider = provider_registry.get(provider_name)

        if not provider.supports_daily_history():
            continue

        if await rate_limiter.is_limited(provider_name):
            errors.append(f"{provider_name}: rate limited")
            continue

        if await provider_health.is_disabled(provider_name):
            errors.append(f"{provider_name}: disabled")
            continue

        try:
            resolved_symbol = await symbol_mapper.resolve(symbol, provider_name)
            fetched_bars = []

            for missing_start, missing_end in missing_ranges:
                bars = await provider.get_daily_history(
                    resolved_symbol, missing_start, missing_end
                )
                fetched_bars.extend(bars)

            normalized_bars = normalize_daily_bars(fetched_bars)
            await price_bar_repo.upsert_daily_bars(symbol=symbol, bars=normalized_bars)

            merged_bars = await price_bar_repo.get_daily_bars(
                symbol=symbol, start_date=start_date, end_date=end_date
            )
            new_coverage = calculate_history_coverage(merged_bars, start_date, end_date)

            if new_coverage >= settings.daily_history_min_coverage_ratio:
                return DailyHistoryResponse(
                    symbol=symbol, bars=merged_bars, coverage=new_coverage,
                    provider_chain_used=["local_cache", provider_name]
                )

            errors.append(f"{provider_name}: coverage still incomplete")

        except ProviderError as error:
            errors.append(f"{provider_name}: {error}")
            await provider_health.record_failure(provider_name, error)

    if local_bars and settings.allow_partial_history:
        return DailyHistoryResponse(
            symbol=symbol, bars=local_bars, coverage=coverage,
            provider_chain_used=["local_cache"],
            warnings=["Partial history only."]
        )

    raise MarketDataUnavailableError(
        symbol=symbol,
        message="No complete daily history available.",
        details={"errors": errors}
    )
```

---
