# Stock Portfolio & Market Data Dashboard — Final Combined Plan

## 1. Project Goal

Build a backend for a personal stock portfolio and stock exploration dashboard with multi-provider market data support.

The system should allow a single user to:

- Manually enter current investments (transactions as source of truth).
- Create and manage portfolios (Main, TFSA, RRSP, FHSA, Taxable, Paper, etc.).
- Create and manage watchlists.
- Track tickers they are following.
- Fetch market data from multiple providers with automatic fallback.
- Cache market data locally for fast lookup.
- Analyze allocation, diversification, risk, and portfolio strength.
- Create "what-if" scenarios before making actual trades.
- Connect a frontend UI to the backend later.

This is a personal, single-user, locally hosted project. It does **not** need tick-by-tick trading-grade data.

The backend needs:

1. Current-ish prices for portfolio allocation.
2. Historical daily prices for risk calculations.
3. Provider fallback when one provider is unavailable or rate-limited.
4. Local cache so provider APIs are not called unnecessarily.

---

## 2. Technology Stack

```text
Backend API:        Python FastAPI
Database:           PostgreSQL + TimescaleDB extension
Background jobs:    Celery
Queue/cache:        Redis
ORM/migrations:     SQLAlchemy + Alembic
Analytics:          pandas / numpy / scipy
Containerization:   Docker Compose
```

---

## 3. High-Level Architecture

```text
                 ┌────────────────────┐
                 │      Frontend      │
                 │ React / Next / etc │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │    API Gateway     │
                 │  FastAPI / REST    │
                 └─────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌────────────────┐  ┌────────────────┐
│ Portfolio     │  │ Market Data    │  │ Analytics/Risk │
│ Service       │  │ Service        │  │ Service        │
└───────┬───────┘  └───────┬────────┘  └───────┬────────┘
        │                  │                   │
        ▼                  ▼                   ▼
┌──────────────────────────────────────────────────────┐
│          PostgreSQL + TimescaleDB                    │
│ portfolios, watchlists, instruments, prices, metrics │
└──────────────────────────────────────────────────────┘
        ▲                  ▲
        │                  │
        ▼                  ▼
┌───────────────┐  ┌────────────────┐
│ Redis Cache   │  │ Celery Worker  │
│ TTL / queues  │  │ Data fetchers  │
└───────────────┘  └────────────────┘
```

---

## 4. Service Boundaries (Modular Monolith)

Start as a single FastAPI application with clear module boundaries:

```text
1. API Gateway          — routing, auth, frontend-friendly responses
2. Portfolio Service    — portfolios, transactions, positions, gains
3. Watchlist Service    — watchlists, items, notes, target prices
4. Instrument Service   — tickers, metadata, tags, metrics
5. Market Data Service  — multi-provider data fetching, caching, normalization
6. Analytics Service    — allocation, risk, diversification, strength scoring
7. Scenario Service     — what-if analysis, comparison
```

Later, split into separate services if needed.

---

## 5. Multi-Provider Market Data Layer

### 5.1 Design Principle

Only `MarketDataService` knows about external providers. Portfolio, Analytics, and Scenario services call:

```python
market_data_service.get_latest_price(symbol)
market_data_service.get_daily_history(symbol, start_date, end_date)
```

They never interact with provider APIs directly.

### 5.2 Architecture

```text
Application Services
        │
        ▼
MarketDataService
        │
        ▼
MarketDataProviderRouter
        │
        ├── AlpacaProvider
        ├── FinnhubProvider
        ├── TwelveDataProvider
        ├── StockDataProvider
        ├── TiingoProvider
        ├── AlphaVantageProvider
        ├── FmpProvider
        └── StooqProvider
```

### 5.3 Latest Price Provider Chain

```text
get_latest_price(symbol):
    1. Check quote cache (latest_price_cache table)
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

### 5.4 Daily Historical Price Provider Chain

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

### 5.5 Provider Interface

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

### 5.6 Normalized Internal Models

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

## 6. Cache Strategy

### 6.1 Durable Cache (PostgreSQL/TimescaleDB)

- Historical price bars (never expire, append/update).
- Fundamental metrics.
- ETF holdings.
- Raw API responses (`api_cache_entries`).
- Fetch job logs.

### 6.2 Short-Lived Cache (Redis)

- Latest quote responses.
- Recently computed portfolio analytics.
- Rate limit counters.
- Background job queue (Celery broker).

### 6.3 Cache TTLs

```text
Latest price (market open):     5 minutes
Latest price (market closed):   60 minutes
Latest price (weekend/holiday): Use last available close
Daily price bars:               Permanent (refresh last 5-10 days for adjustments)
Company overview:               7 days
ETF profile:                    7 days
Financial statements:           30 days
Portfolio analytics:            1-5 minutes
Scenario analytics:             1-5 minutes
Symbol search results:          7 days
```

### 6.4 Staleness Policy

```yaml
allow_stale_latest_price: true
max_stale_latest_price_hours: 24
allow_partial_history: true
daily_history_min_coverage_ratio: 0.95
```

---

## 7. Rate Limiting & Provider Health

### 7.1 Per-Provider Rate Limiting

Each provider has configurable rate limit rules (requests per minute, per day, per endpoint). If a provider is rate-limited, the router skips it and tries the next.

### 7.2 Circuit Breaker

```text
3 consecutive failures → mark provider as degraded
5 consecutive failures → disable provider for 15 minutes
Rate-limit error       → disable until window resets
```

### 7.3 Provider Health Tracking

Track per-provider: status (healthy/degraded/rate_limited/disabled/failing), last success/failure timestamps, consecutive failure count.

---

## 8. Provider Configuration

Provider chain order and cache settings live in a **YAML config file only** (requires app restart to change). Database tables are used only for runtime state (health, request logs, rate limit tracking) — not for chain order.

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

## 9. Database Schema

### 9.1 Core Tables

| Table | Purpose |
|---|---|
| `users` | User profile (single-user for now, future-proof) |
| `portfolios` | Portfolio containers (Main, TFSA, RRSP, etc.) |
| `portfolio_transactions` | Source of truth for holdings (BUY, SELL, DIVIDEND, SPLIT, etc.) |
| `instruments` | All tickers (owned, watched, searched) |
| `provider_symbol_mappings` | Provider-specific symbol formats per instrument (e.g. SHOP.TO → SHOP.TRT for Alpha Vantage) |
| `watchlists` | Watchlist containers |
| `watchlist_items` | Tickers in watchlists with notes/target prices |
| `tags` | Flexible categorization (sector, theme, strategy, etc.) |
| `instrument_tags` | Many-to-many instrument-tag mapping |

`provider_symbol_mappings` schema:

```sql
CREATE TABLE provider_symbol_mappings (
    id UUID PRIMARY KEY,
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(instrument_id, provider)
);
```

This supports multi-exchange and multi-country tickers from Phase 1 (e.g., Canadian tickers with different provider formats).

### 9.2 Market Data Tables

| Table | Purpose |
|---|---|
| `price_bars` | Historical OHLCV (TimescaleDB hypertable, `source` required — no default) |
| `quote_snapshots` | Historical quote archive |
| `latest_price_cache` | Fast lookup for allocation (one row per instrument) |
| `api_cache_entries` | Raw API response cache |
| `market_data_fetch_jobs` | Fetch job tracking |

### 9.3 Multi-Provider Tables

| Table | Purpose |
|---|---|
| `market_data_providers` | Provider registry (name, capabilities, priority) |
| `market_data_provider_credentials` | Env var names for API keys (not raw keys) |
| `provider_rate_limit_rules` | Configurable rate limits per provider |
| `provider_request_log` | Request audit trail |
| `provider_health_state` | Runtime health/circuit breaker state |

### 9.4 Analytics & Scenario Tables

| Table | Purpose |
|---|---|
| `metric_definitions` | Metric codes and metadata |
| `instrument_metric_snapshots` | Point-in-time metric values per instrument |
| `etf_holdings` | ETF underlying holdings for look-through analysis |
| `scenarios` | What-if scenario containers |
| `scenario_items` | Individual scenario actions |
| `portfolio_snapshots` | Time-series of portfolio value/metrics |

### 9.5 Views

- `current_positions` — derived from `portfolio_transactions`
- `latest_quotes` — most recent quote per instrument

---

## 10. REST API Design

### 10.1 Portfolio APIs

```http
POST   /api/portfolios
GET    /api/portfolios
GET    /api/portfolios/{portfolio_id}
DELETE /api/portfolios/{portfolio_id}

POST   /api/portfolios/{portfolio_id}/transactions
GET    /api/portfolios/{portfolio_id}/transactions
PUT    /api/transactions/{transaction_id}
DELETE /api/transactions/{transaction_id}

GET    /api/portfolios/{portfolio_id}/positions
GET    /api/portfolios/{portfolio_id}/allocation
GET    /api/portfolios/{portfolio_id}/performance
GET    /api/portfolios/{portfolio_id}/risk
```

### 10.2 Watchlist APIs

```http
POST   /api/watchlists
GET    /api/watchlists
GET    /api/watchlists/{watchlist_id}
POST   /api/watchlists/{watchlist_id}/items
DELETE /api/watchlists/{watchlist_id}/items/{instrument_id}
GET    /api/watchlists/{watchlist_id}/analytics
```

### 10.3 Instrument APIs

```http
GET  /api/instruments/search?query=nvda
GET  /api/instruments/{instrument_id}
POST /api/instruments/{instrument_id}/tags
GET  /api/instruments/{instrument_id}/metrics
GET  /api/instruments/{instrument_id}/prices?timeframe=1d
```

### 10.4 Market Data APIs

```http
GET  /api/market-data/latest-price/{symbol}
POST /api/market-data/latest-prices              (batch)
GET  /api/market-data/daily-history/{symbol}?start_date=...&end_date=...
POST /api/market-data/refresh/{symbol}
POST /api/market-data/refresh-portfolio/{portfolio_id}
POST /api/market-data/refresh-watchlist/{watchlist_id}
GET  /api/market-data/providers/status
```

### 10.5 Scenario APIs

```http
POST /api/scenarios
GET  /api/scenarios?portfolio_id=...
GET  /api/scenarios/{scenario_id}
POST /api/scenarios/{scenario_id}/items
GET  /api/scenarios/{scenario_id}/analysis
POST /api/scenarios/{scenario_id}/compare
```

---

## 11. Analytics & Risk

### 11.1 Allocation Metrics

- Market value by ticker, sector, industry, tag/theme, currency, asset type.
- Top 3/5 holdings concentration.
- Single-position concentration.

### 11.2 Risk Metrics

- Daily returns.
- Annualized volatility.
- Beta (against SPY/QQQ/VTI).
- Correlation matrix.
- Max drawdown.
- Historical Value at Risk (95%).
- Sharpe ratio.

Use `adjusted_close` when available (`adjusted_close > close`).

### 11.3 Diversification Metrics

- Number of holdings.
- Sector/theme concentration.
- Herfindahl-Hirschman Index.
- ETF overlap (later).

### 11.4 Fundamental Strength Metrics

- **Valuation:** P/E, PEG, P/S, P/B.
- **Growth:** Revenue growth, EPS growth.
- **Profitability:** Profit margin, operating margin, ROE.
- **Balance sheet:** Debt/equity, current ratio.
- **Market risk:** Beta, volatility, drawdown.
- **Income:** Dividend yield, payout ratio.

### 11.5 Portfolio Strength Score

```text
Portfolio Strength Score =
  25% diversification score
+ 25% risk score
+ 20% profitability score
+ 15% growth score
+ 15% valuation score
```

Personal analytical model for consistent scenario comparison.

---

## 12. Scenario Service

- Create scenario portfolios without mutating real data.
- Actions: ADD_POSITION, INCREASE_POSITION, REDUCE_POSITION, REMOVE_POSITION, SET_TARGET_WEIGHT.
- Compare current vs scenario on all analytics dimensions.
- Pull watchlist tickers into scenarios.

---

## 13. Background Jobs (Celery)

### Daily after market close:
- Refresh daily bars for portfolio + watchlist holdings.
- Recalculate portfolio snapshots.
- Recalculate risk metrics.

### During market hours:
- Refresh latest prices for portfolio holdings every 5-15 minutes.
- Refresh watchlist latest prices less frequently.

### Weekly:
- Refresh company overview/fundamentals.
- Refresh ETF profiles.
- Refresh provider metadata.

### On app open:
- Load cached latest prices.
- Queue quote refresh only if rate limits allow.
- Warn user when data is stale.

---

## 14. Data Quality Flags

Every returned price/history result should include quality metadata:

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

If data is stale, the frontend gets a clear signal:

```json
{
  "data_status": "stale",
  "warning": "Live quote providers unavailable. Using latest daily close."
}
```

---

## 15. Error Handling

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

The frontend does not see individual provider failures — only aggregated data status.

---

## 16. Project Structure

```text
stock-dashboard-backend/
├── docker-compose.yml
├── .env.example
├── README.md
├── config/
│   └── market_data.yaml
│
├── services/
│   ├── api_gateway/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── dependencies.py
│   │
│   ├── portfolio_service/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── routes.py
│   │
│   ├── watchlist_service/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── routes.py
│   │
│   ├── instrument_service/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── routes.py
│   │
│   ├── market_data_service/
│   │   ├── service.py
│   │   ├── provider_router.py
│   │   ├── cache_policy.py
│   │   ├── freshness_policy.py
│   │   ├── normalizers.py
│   │   ├── exceptions.py
│   │   ├── routes.py
│   │   │
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
│   │   │
│   │   └── schemas/
│   │       ├── latest_price.py
│   │       ├── price_bar.py
│   │       └── provider_result.py
│   │
│   ├── analytics_service/
│   │   ├── risk.py
│   │   ├── allocation.py
│   │   ├── performance.py
│   │   ├── strength.py
│   │   └── routes.py
│   │
│   └── scenario_service/
│       ├── service.py
│       └── routes.py
│
├── shared/
│   ├── db.py
│   ├── settings.py
│   ├── models/
│   └── utils/
│
├── workers/
│   ├── celery_app.py
│   ├── market_data_tasks.py
│   └── analytics_tasks.py
│
├── migrations/
└── tests/
```

---

## 17. Docker Compose

```yaml
services:
  api:
    build: ./services/api_gateway
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
      - redis

  worker:
    build: ./workers
    env_file:
      - .env
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

## 18. Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://stock_user:stock_password@db:5432/stock_dashboard
REDIS_URL=redis://redis:6379/0

ALPACA_API_KEY=
ALPACA_API_SECRET=
FINNHUB_API_KEY=
TWELVEDATA_API_KEY=
STOCKDATA_API_KEY=
TIINGO_API_KEY=
ALPHA_VANTAGE_API_KEY=
FMP_API_KEY=
```

---

## 19. Implementation Roadmap

### Phase 1: Core Portfolio Backend

- Users, portfolios, instruments tables.
- `provider_symbol_mappings` table (multi-exchange/multi-country from day one).
- Manual transactions.
- Current positions view.
- Basic REST API (CRUD).
- Docker Compose setup.

**Goal:** Manually enter holdings and see current positions.

### Phase 2: Market Data Provider Layer

- Base provider interface + provider registry.
- Provider router with fallback logic.
- Normalized price models (LatestPrice, DailyPriceBar).
- `latest_price_cache` and `price_bars` tables.
- Cache freshness policy.
- First provider: Alpha Vantage (daily history).
- Second provider: Alpaca (latest price).

**Goal:** `get_latest_price()` and `get_daily_history()` work with at least 2 providers.

### Phase 3: Allocation & Analytics

- Batch latest price lookup.
- Position market value calculation.
- Allocation by ticker, sector, asset type, tag.
- Top holding concentration.

**Goal:** See risk allocation based on cached/latest prices.

### Phase 4: Watchlists & Scenarios

- Watchlist tables + APIs.
- Scenario tables + APIs.
- Scenario analysis endpoint.
- Current vs scenario comparison.

**Goal:** Preview buying, selling, or rebalancing before making trades.

### Phase 5: Risk Engine

- Daily returns calculation.
- Annualized volatility, beta, max drawdown.
- Correlation matrix.
- Historical VaR, Sharpe ratio.
- Portfolio snapshots.

**Goal:** Evaluate portfolio risk and compare scenarios.

### Phase 6: Full Provider Chain & Health

- Add remaining providers (Finnhub, Twelve Data, StockData, Tiingo, FMP, Stooq).
- Provider rate limit rules + request logging.
- Provider health state + circuit breaker.
- Skip unhealthy/exhausted providers automatically.

**Goal:** System is resilient to any single provider being down.

### Phase 7: Strength Scoring & Fundamentals

- Metric definitions + metric snapshots.
- Normalized metric scoring.
- Portfolio strength score.
- ETF holdings for look-through analysis (later).

**Goal:** Compare portfolio quality using a consistent scoring model.

---

## 20. Future Enhancements

- Multi-user support / OAuth.
- Broker integration.
- Import transactions from CSV.
- Tax reporting (Canadian vs US accounts).
- Currency conversion.
- Dividend tracking.
- ETF look-through allocation.
- Risk alerts.
- Rebalancing recommendations.
- AI-assisted portfolio explanations / local LLM.
- News sentiment, earnings calendar.
- Backtesting / portfolio optimization.
- Mobile UI.

---

## 21. Authentication (Deferred)

For local single-user, start with no auth or a static API token. Create a `users` table now for future expansion.

---

## Appendix A: Full Database DDL

### A.1 Users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### A.2 Portfolios

```sql
CREATE TABLE portfolios (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    description TEXT,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### A.3 Instruments

```sql
CREATE TABLE instruments (
    id UUID PRIMARY KEY,
    symbol TEXT NOT NULL,
    normalized_symbol TEXT NOT NULL,
    name TEXT,
    asset_type TEXT NOT NULL,
    exchange TEXT,
    currency TEXT,
    country TEXT,
    sector TEXT,
    industry TEXT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(normalized_symbol, exchange)
);
```

### A.4 Provider Symbol Mappings

```sql
CREATE TABLE provider_symbol_mappings (
    id UUID PRIMARY KEY,
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(instrument_id, provider)
);
```

### A.5 Portfolio Transactions

```sql
CREATE TABLE portfolio_transactions (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id),
    instrument_id UUID NOT NULL REFERENCES instruments(id),

    transaction_type TEXT NOT NULL,
    -- BUY, SELL, DIVIDEND, SPLIT, FEE, CASH_DEPOSIT, CASH_WITHDRAWAL

    trade_date TIMESTAMPTZ NOT NULL,
    settlement_date TIMESTAMPTZ,

    quantity NUMERIC(24, 8),
    price NUMERIC(24, 8),
    gross_amount NUMERIC(24, 8),
    fees NUMERIC(24, 8) DEFAULT 0,

    currency TEXT NOT NULL DEFAULT 'USD',
    fx_rate_to_portfolio_currency NUMERIC(24, 10),

    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Transaction types:

```text
BUY
SELL
DIVIDEND
SPLIT
FEE
CASH_DEPOSIT
CASH_WITHDRAWAL
```

### A.6 Current Positions View

```sql
CREATE VIEW current_positions AS
SELECT
    portfolio_id,
    instrument_id,
    SUM(
        CASE
            WHEN transaction_type = 'BUY' THEN quantity
            WHEN transaction_type = 'SELL' THEN -quantity
            ELSE 0
        END
    ) AS quantity
FROM portfolio_transactions
GROUP BY portfolio_id, instrument_id
HAVING SUM(
    CASE
        WHEN transaction_type = 'BUY' THEN quantity
        WHEN transaction_type = 'SELL' THEN -quantity
        ELSE 0
    END
) <> 0;
```

### A.7 Watchlists

```sql
CREATE TABLE watchlists (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watchlist_items (
    id UUID PRIMARY KEY,
    watchlist_id UUID NOT NULL REFERENCES watchlists(id),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    target_buy_price NUMERIC(24, 8),
    priority TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(watchlist_id, instrument_id)
);
```

Priority values: `low`, `medium`, `high`, `urgent`

### A.8 Price Bars

```sql
CREATE TABLE price_bars (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
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

    PRIMARY KEY (instrument_id, timeframe, ts)
);

SELECT create_hypertable('price_bars', 'ts');
```

Timeframe values (start with `1d` only):

```text
1d
1h
15m
5m
1m
```

### A.9 Quote Snapshots

```sql
CREATE TABLE quote_snapshots (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    ts TIMESTAMPTZ NOT NULL,

    price NUMERIC(24, 8),
    open NUMERIC(24, 8),
    high NUMERIC(24, 8),
    low NUMERIC(24, 8),
    previous_close NUMERIC(24, 8),
    volume BIGINT,

    source TEXT NOT NULL,
    raw_payload JSONB,

    PRIMARY KEY (instrument_id, ts)
);

CREATE VIEW latest_quotes AS
SELECT DISTINCT ON (instrument_id)
    instrument_id,
    ts,
    price,
    open,
    high,
    low,
    previous_close,
    volume
FROM quote_snapshots
ORDER BY instrument_id, ts DESC;
```

### A.10 Latest Price Cache

```sql
CREATE TABLE latest_price_cache (
    instrument_id UUID PRIMARY KEY REFERENCES instruments(id),

    symbol TEXT NOT NULL,
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
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### A.11 API Cache Entries

```sql
CREATE TABLE api_cache_entries (
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

### A.12 Market Data Fetch Jobs

```sql
CREATE TABLE market_data_fetch_jobs (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    instrument_id UUID REFERENCES instruments(id),
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

### A.13 Market Data Providers

```sql
CREATE TABLE market_data_providers (
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

### A.14 Provider Credentials

```sql
CREATE TABLE market_data_provider_credentials (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data_providers(id),

    credential_name TEXT NOT NULL,
    env_var_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(provider_id, credential_name)
);
```

### A.15 Provider Rate Limit Rules

```sql
CREATE TABLE provider_rate_limit_rules (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data_providers(id),

    rule_name TEXT NOT NULL,
    max_requests INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,

    applies_to_endpoint TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example values:

```text
alpaca:    free_plan_per_minute    200 requests / 60 seconds
finnhub:   free_plan_per_minute    60 requests / 60 seconds
```

### A.16 Provider Request Log

```sql
CREATE TABLE provider_request_log (
    id UUID PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES market_data_providers(id),

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

### A.17 Provider Health State

```sql
CREATE TABLE provider_health_state (
    provider_id UUID PRIMARY KEY REFERENCES market_data_providers(id),

    status TEXT NOT NULL,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    disabled_until TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Status values: `healthy`, `degraded`, `rate_limited`, `disabled`, `failing`

### A.18 Tags

```sql
CREATE TABLE tags (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    tag_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE instrument_tags (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    tag_id UUID NOT NULL REFERENCES tags(id),
    source TEXT NOT NULL DEFAULT 'manual',
    PRIMARY KEY (instrument_id, tag_id)
);
```

Tag types: `sector`, `theme`, `risk_type`, `strategy`, `currency`, `custom`

### A.19 Metric Definitions

```sql
CREATE TABLE metric_definitions (
    id UUID PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    metric_group TEXT NOT NULL,
    unit TEXT,
    higher_is_better BOOLEAN
);
```

Example metric codes:

```text
pe_ratio
peg_ratio
profit_margin
operating_margin
return_on_equity
debt_to_equity
revenue_growth_yoy
earnings_growth_yoy
dividend_yield
beta
market_cap
price_to_book
price_to_sales
```

### A.20 Instrument Metric Snapshots

```sql
CREATE TABLE instrument_metric_snapshots (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    metric_id UUID NOT NULL REFERENCES metric_definitions(id),
    as_of_date DATE NOT NULL,
    value NUMERIC(30, 10),
    source TEXT NOT NULL,
    raw_value TEXT,

    PRIMARY KEY (instrument_id, metric_id, as_of_date)
);
```

### A.21 ETF Holdings

```sql
CREATE TABLE etf_holdings (
    etf_instrument_id UUID NOT NULL REFERENCES instruments(id),
    holding_symbol TEXT NOT NULL,
    holding_name TEXT,
    holding_instrument_id UUID REFERENCES instruments(id),
    weight NUMERIC(12, 8),
    sector TEXT,
    asset_type TEXT,
    as_of_date DATE NOT NULL,
    source TEXT NOT NULL,

    PRIMARY KEY (etf_instrument_id, holding_symbol, as_of_date)
);
```

### A.22 Scenarios

```sql
CREATE TABLE scenarios (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id),
    name TEXT NOT NULL,
    description TEXT,
    base_snapshot_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE scenario_items (
    id UUID PRIMARY KEY,
    scenario_id UUID NOT NULL REFERENCES scenarios(id),
    instrument_id UUID NOT NULL REFERENCES instruments(id),

    action_type TEXT NOT NULL,
    quantity_delta NUMERIC(24, 8),
    cash_amount_delta NUMERIC(24, 8),
    target_weight NUMERIC(12, 8),
    assumed_price NUMERIC(24, 8),

    notes TEXT
);
```

Action types: `ADD_POSITION`, `INCREASE_POSITION`, `REDUCE_POSITION`, `REMOVE_POSITION`, `SET_TARGET_WEIGHT`

### A.23 Portfolio Snapshots

```sql
CREATE TABLE portfolio_snapshots (
    portfolio_id UUID NOT NULL REFERENCES portfolios(id),
    ts TIMESTAMPTZ NOT NULL,

    total_market_value NUMERIC(24, 8),
    cash_value NUMERIC(24, 8),
    invested_value NUMERIC(24, 8),
    unrealized_gain_loss NUMERIC(24, 8),
    day_change_value NUMERIC(24, 8),
    day_change_percent NUMERIC(12, 8),

    metrics JSONB,

    PRIMARY KEY (portfolio_id, ts)
);
```

---

## Appendix B: Key Pseudocode

### B.1 get_latest_price

```python
async def get_latest_price(symbol: str) -> LatestPrice:
    instrument = await instrument_repo.get_by_symbol(symbol)

    cached = await latest_price_cache_repo.get(instrument.id)

    if cached and cached.expires_at > now():
        return cached.to_latest_price()

    provider_chain = [
        "alpaca",
        "finnhub",
        "twelvedata",
        "stockdata",
    ]

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
            latest_price = await provider.get_latest_price(symbol)

            await latest_price_cache_repo.upsert(
                instrument_id=instrument.id,
                latest_price=latest_price,
                ttl_minutes=get_latest_price_ttl()
            )

            await quote_snapshot_repo.insert(
                instrument_id=instrument.id,
                latest_price=latest_price
            )

            return latest_price

        except ProviderError as error:
            errors.append(f"{provider_name}: {error}")
            await provider_health.record_failure(provider_name, error)

    # Final fallback: latest daily close
    fallback = await price_bar_repo.get_latest_daily_close(instrument.id)

    if fallback:
        return LatestPrice(
            symbol=symbol,
            provider="daily_close_fallback",
            price=fallback.adjusted_close or fallback.close,
            currency=instrument.currency,
            as_of=fallback.ts,
            is_realtime=False,
            is_delayed=True,
            delay_minutes=None,
            raw_payload={"fallback": True, "errors": errors}
        )

    raise MarketDataUnavailableError(
        symbol=symbol,
        message="No latest price available from cache, providers, or daily close fallback."
    )
```

### B.2 get_daily_history

```python
async def get_daily_history(
    symbol: str,
    start_date: date,
    end_date: date
) -> list[DailyPriceBar]:

    instrument = await instrument_repo.get_by_symbol(symbol)

    local_bars = await price_bar_repo.get_daily_bars(
        instrument_id=instrument.id,
        start_date=start_date,
        end_date=end_date
    )

    coverage = calculate_history_coverage(
        bars=local_bars,
        start_date=start_date,
        end_date=end_date
    )

    if coverage >= settings.daily_history_min_coverage_ratio:
        return local_bars

    missing_ranges = calculate_missing_ranges(
        bars=local_bars,
        start_date=start_date,
        end_date=end_date
    )

    provider_chain = [
        "tiingo",
        "alpha_vantage",
        "fmp",
        "twelvedata",
        "stooq",
    ]

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
            fetched_bars = []

            for missing_start, missing_end in missing_ranges:
                bars = await provider.get_daily_history(
                    symbol=symbol,
                    start_date=missing_start,
                    end_date=missing_end
                )
                fetched_bars.extend(bars)

            normalized_bars = normalize_daily_bars(fetched_bars)

            await price_bar_repo.upsert_daily_bars(
                instrument_id=instrument.id,
                bars=normalized_bars
            )

            merged_bars = await price_bar_repo.get_daily_bars(
                instrument_id=instrument.id,
                start_date=start_date,
                end_date=end_date
            )

            new_coverage = calculate_history_coverage(
                bars=merged_bars,
                start_date=start_date,
                end_date=end_date
            )

            if new_coverage >= settings.daily_history_min_coverage_ratio:
                return merged_bars

            errors.append(
                f"{provider_name}: fetched data but coverage still incomplete"
            )

        except ProviderError as error:
            errors.append(f"{provider_name}: {error}")
            await provider_health.record_failure(provider_name, error)

    if local_bars and settings.allow_partial_history:
        return local_bars

    raise MarketDataUnavailableError(
        symbol=symbol,
        message="No complete daily history available.",
        details={"errors": errors}
    )
```

---

## Appendix C: Ingestion Triggers

### C.1 When a Ticker Is Added to a Portfolio

```text
1. Create or find instrument.
2. Create provider_symbol_mappings if needed.
3. Queue company overview fetch.
4. Queue daily price history fetch.
5. Queue latest quote fetch.
6. Store raw API response in api_cache_entries.
7. Normalize response into price_bars / quote_snapshots / metrics.
8. Mark fetch job as successful or failed.
```

### C.2 When a Ticker Is Added to a Watchlist

```text
1. Create or find instrument.
2. Fetch overview if missing.
3. Fetch daily history if missing.
4. Fetch latest quote only if cache expired.
5. Save data locally.
```

### C.3 When a Ticker Is Searched

```text
1. Check local instruments first.
2. If not found, call provider symbol search.
3. Save lookup result locally.
4. Do NOT fetch full history until user adds to portfolio or watchlist.
```

---