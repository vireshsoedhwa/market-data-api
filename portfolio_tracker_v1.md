# Portfolio Tracker API — Plan v1

## 1. Service Goal

The main application backend for a personal stock portfolio and stock exploration dashboard.

It owns portfolios, transactions, watchlists, scenarios, analytics, and risk calculations. It does **not** contain provider-specific code — instead it calls the Market Data API over HTTP for all market data needs.

---

## 2. Technology Stack

```text
Framework:          Python FastAPI (port 8000)
Database:           PostgreSQL + TimescaleDB (portfolio schema)
Background jobs:    Celery (portfolio-worker)
Queue/cache:        Redis
ORM/migrations:    SQLAlchemy + Alembic
Analytics:          pandas / numpy / scipy
HTTP client:        httpx (calls Market Data API)
Containerization:   Docker Compose
```

---

## 3. High-Level Architecture

```text
Frontend
   │
   ▼
Portfolio API (port 8000)
- portfolios, transactions
- watchlists, scenarios
- allocation, risk analytics
- portfolio snapshots
   │
   │ HTTP calls (internal)
   ▼
Market Data API (port 8010)
- latest prices
- historical bars
- provider routing & fallback
```

The key principle:

```text
Portfolio API asks: "What market data do I need?" (passes symbols)
Market Data API answers: "Here is the best available normalized market data."
```

---

## 4. Service Responsibilities

The Portfolio API owns:

```text
users
portfolios
portfolio_transactions
current_positions
watchlists
watchlist_items
instruments (basic metadata, tags)
scenarios
scenario_items
portfolio analytics (allocation, risk, diversification, strength)
portfolio snapshots
tags / instrument_tags
metric_definitions / instrument_metric_snapshots
etf_holdings
```

It should **not** contain provider-specific code. It should **not** directly call Alpaca, Finnhub, Tiingo, etc.

Instead, it calls the Market Data API over HTTP using a `MarketDataClient`.

---

## 5. Main Design Rule

The Portfolio API translates portfolios and watchlists into symbol lists, then calls the Market Data API with symbols.

```text
Portfolio API:  "What do I own, and how should I analyze it?"
Market Data API: "What is the best available market data for this symbol?"
```

The Market Data API must not know about portfolios or watchlists.

---

## 6. Communication with Market Data API

Instead of in-process Python calls:

```python
# OLD (monolith style)
market_data_service.get_latest_price("NVDA")
```

The Portfolio API calls the Market Data API over HTTP:

```http
GET http://market-data-api:8010/v1/quotes/NVDA
```

For batch requests:

```http
POST http://market-data-api:8010/v1/quotes/batch
{"symbols": ["NVDA", "AAPL", "IONQ", "QBTS"]}
```

---

## 7. Internal Market Data Client

The Portfolio API uses a client class to call the Market Data API:

```python
import httpx
from datetime import date


class MarketDataClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout_seconds

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    async def get_latest_price(self, symbol: str, exchange: str | None = None):
        params = {}
        if exchange:
            params["exchange"] = exchange

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/quotes/{symbol}",
                params=params,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_latest_prices(self, symbols: list[str]):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/quotes/batch",
                json={"symbols": symbols},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_daily_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
    ):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/history/{symbol}",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timeframe": timeframe,
                },
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()
```

---

## 8. API Endpoints

### 8.1 Portfolio APIs

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

### 8.2 Watchlist APIs

```http
POST   /api/watchlists
GET    /api/watchlists
GET    /api/watchlists/{watchlist_id}
POST   /api/watchlists/{watchlist_id}/items
DELETE /api/watchlists/{watchlist_id}/items/{instrument_id}
GET    /api/watchlists/{watchlist_id}/analytics
```

### 8.3 Instrument APIs

```http
GET  /api/instruments/search?query=nvda
GET  /api/instruments/{instrument_id}
POST /api/instruments/{instrument_id}/tags
GET  /api/instruments/{instrument_id}/metrics
GET  /api/instruments/{instrument_id}/prices?timeframe=1d
```

### 8.4 Scenario APIs

```http
POST /api/scenarios
GET  /api/scenarios?portfolio_id=...
GET  /api/scenarios/{scenario_id}
POST /api/scenarios/{scenario_id}/items
GET  /api/scenarios/{scenario_id}/analysis
POST /api/scenarios/{scenario_id}/compare
```

---

## 9. Analytics & Risk

### 9.1 Allocation Metrics

- Market value by ticker, sector, industry, tag/theme, currency, asset type.
- Top 3/5 holdings concentration.
- Single-position concentration.

### 9.2 Risk Metrics

- Daily returns.
- Annualized volatility.
- Beta (against SPY/QQQ/VTI).
- Correlation matrix.
- Max drawdown.
- Historical Value at Risk (95%).
- Sharpe ratio.

Use `adjusted_close` when available (`adjusted_close > close`).

### 9.3 Diversification Metrics

- Number of holdings.
- Sector/theme concentration.
- Herfindahl-Hirschman Index.
- ETF overlap (later).

### 9.4 Fundamental Strength Metrics

- **Valuation:** P/E, PEG, P/S, P/B.
- **Growth:** Revenue growth, EPS growth.
- **Profitability:** Profit margin, operating margin, ROE.
- **Balance sheet:** Debt/equity, current ratio.
- **Market risk:** Beta, volatility, drawdown.
- **Income:** Dividend yield, payout ratio.

### 9.5 Portfolio Strength Score

```text
Portfolio Strength Score =
  25% diversification score
+ 25% risk score
+ 20% profitability score
+ 15% growth score
+ 15% valuation score
```

Personal analytical model for consistent scenario comparison.

### 9.6 Allocation Flow

```text
Portfolio API:
1. Reads current_positions from portfolio schema.
2. Extracts symbols.
3. Calls Market Data API: POST /v1/quotes/batch {symbols: [...]}
4. Combines positions + prices.
5. Calculates allocation.
6. Returns allocation to frontend.
```

### 9.7 Risk Analytics Flow

```text
Portfolio API / Analytics Service:
1. Reads holdings.
2. Calls Market Data API: GET /v1/history/{symbol} for each symbol.
3. Receives normalized adjusted close data.
4. Calculates returns, volatility, beta, drawdown, VaR, Sharpe ratio.
5. Stores portfolio-level snapshots and metrics.
```

---

## 10. Scenario Service

- Create scenario portfolios without mutating real data.
- Actions: ADD_POSITION, INCREASE_POSITION, REDUCE_POSITION, REMOVE_POSITION, SET_TARGET_WEIGHT.
- Compare current vs scenario on all analytics dimensions.
- Pull watchlist tickers into scenarios.

---

## 11. Background Jobs (Portfolio Worker)

### 11.1 Responsibilities

```text
portfolio snapshots
risk metric recalculation
scenario comparison
allocation snapshots
```

The Portfolio Worker may call the Market Data API over HTTP, but it should **not** call market data providers directly.

### 11.2 Schedules

**Daily after market close:**
- Recalculate portfolio snapshots + risk metrics (after Market Data Worker refreshes daily bars).

---

## 12. Cache Strategy (Portfolio side)

### 12.1 Durable Cache (PostgreSQL — portfolio schema)

- Fundamental metrics.
- ETF holdings.
- Portfolio snapshots.

### 12.2 Short-Lived Cache (Redis)

- Recently computed portfolio analytics.
- Background job queues (Celery broker).

### 12.3 Cache TTLs

```text
Portfolio analytics:            1-5 minutes
Scenario analytics:             1-5 minutes
Company overview:               7 days
ETF profile:                    7 days
Financial statements:           30 days
```

---

## 13. Database Schema (portfolio)

### 13.1 Users

```sql
CREATE SCHEMA IF NOT EXISTS portfolio;

CREATE TABLE portfolio.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 13.2 Portfolios

```sql
CREATE TABLE portfolio.portfolios (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES portfolio.users(id),
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    description TEXT,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 13.3 Instruments

```sql
CREATE TABLE portfolio.instruments (
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

### 13.4 Portfolio Transactions

```sql
CREATE TABLE portfolio.portfolio_transactions (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolio.portfolios(id),
    instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),

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

Transaction types: `BUY`, `SELL`, `DIVIDEND`, `SPLIT`, `FEE`, `CASH_DEPOSIT`, `CASH_WITHDRAWAL`

### 13.5 Current Positions View

```sql
CREATE VIEW portfolio.current_positions AS
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
FROM portfolio.portfolio_transactions
GROUP BY portfolio_id, instrument_id
HAVING SUM(
    CASE
        WHEN transaction_type = 'BUY' THEN quantity
        WHEN transaction_type = 'SELL' THEN -quantity
        ELSE 0
    END
) <> 0;
```

### 13.6 Watchlists

```sql
CREATE TABLE portfolio.watchlists (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES portfolio.users(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolio.watchlist_items (
    id UUID PRIMARY KEY,
    watchlist_id UUID NOT NULL REFERENCES portfolio.watchlists(id),
    instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),
    target_buy_price NUMERIC(24, 8),
    priority TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(watchlist_id, instrument_id)
);
```

Priority values: `low`, `medium`, `high`, `urgent`

### 13.7 Tags

```sql
CREATE TABLE portfolio.tags (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES portfolio.users(id),
    name TEXT NOT NULL,
    tag_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolio.instrument_tags (
    instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),
    tag_id UUID NOT NULL REFERENCES portfolio.tags(id),
    source TEXT NOT NULL DEFAULT 'manual',
    PRIMARY KEY (instrument_id, tag_id)
);
```

Tag types: `sector`, `theme`, `risk_type`, `strategy`, `currency`, `custom`

### 13.8 Metric Definitions

```sql
CREATE TABLE portfolio.metric_definitions (
    id UUID PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    metric_group TEXT NOT NULL,
    unit TEXT,
    higher_is_better BOOLEAN
);
```

Example metric codes: `pe_ratio`, `peg_ratio`, `profit_margin`, `operating_margin`, `return_on_equity`, `debt_to_equity`, `revenue_growth_yoy`, `earnings_growth_yoy`, `dividend_yield`, `beta`, `market_cap`, `price_to_book`, `price_to_sales`

### 13.9 Instrument Metric Snapshots

```sql
CREATE TABLE portfolio.instrument_metric_snapshots (
    instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),
    metric_id UUID NOT NULL REFERENCES portfolio.metric_definitions(id),
    as_of_date DATE NOT NULL,
    value NUMERIC(30, 10),
    source TEXT NOT NULL,
    raw_value TEXT,

    PRIMARY KEY (instrument_id, metric_id, as_of_date)
);
```

### 13.10 ETF Holdings

```sql
CREATE TABLE portfolio.etf_holdings (
    etf_instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),
    holding_symbol TEXT NOT NULL,
    holding_name TEXT,
    holding_instrument_id UUID REFERENCES portfolio.instruments(id),
    weight NUMERIC(12, 8),
    sector TEXT,
    asset_type TEXT,
    as_of_date DATE NOT NULL,
    source TEXT NOT NULL,

    PRIMARY KEY (etf_instrument_id, holding_symbol, as_of_date)
);
```

### 13.11 Scenarios

```sql
CREATE TABLE portfolio.scenarios (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolio.portfolios(id),
    name TEXT NOT NULL,
    description TEXT,
    base_snapshot_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolio.scenario_items (
    id UUID PRIMARY KEY,
    scenario_id UUID NOT NULL REFERENCES portfolio.scenarios(id),
    instrument_id UUID NOT NULL REFERENCES portfolio.instruments(id),

    action_type TEXT NOT NULL,
    quantity_delta NUMERIC(24, 8),
    cash_amount_delta NUMERIC(24, 8),
    target_weight NUMERIC(12, 8),
    assumed_price NUMERIC(24, 8),

    notes TEXT
);
```

Action types: `ADD_POSITION`, `INCREASE_POSITION`, `REDUCE_POSITION`, `REMOVE_POSITION`, `SET_TARGET_WEIGHT`

### 13.12 Portfolio Snapshots

```sql
CREATE TABLE portfolio.portfolio_snapshots (
    portfolio_id UUID NOT NULL REFERENCES portfolio.portfolios(id),
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

## 14. Environment Variables (.env)

```bash
DATABASE_URL=postgresql+asyncpg://stock_user:stock_password@db:5432/stock_dashboard
REDIS_URL=redis://redis:6379/0
MARKET_DATA_BASE_URL=http://market-data-api:8010
MARKET_DATA_INTERNAL_API_KEY=change-me
```

---

## 15. Project Structure

```text
apps/
├── portfolio-api/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── portfolios.py
│   │   │   ├── transactions.py
│   │   │   ├── watchlists.py
│   │   │   ├── instruments.py
│   │   │   ├── scenarios.py
│   │   │   └── analytics.py
│   │   ├── services/
│   │   │   ├── portfolio_service.py
│   │   │   ├── watchlist_service.py
│   │   │   ├── analytics_service.py
│   │   │   └── scenario_service.py
│   │   ├── models/
│   │   ├── schemas/
│   │   └── clients/
│   │       └── market_data_client.py
│   ├── Dockerfile
│   └── requirements.txt
│
└── portfolio-worker/
    ├── app/
    │   ├── celery_app.py
    │   └── tasks.py
    └── Dockerfile
```

---

## 16. Docker Compose (Portfolio services)

```yaml
services:
  portfolio-api:
    build: ./apps/portfolio-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      MARKET_DATA_BASE_URL: http://market-data-api:8010
    depends_on:
      - db
      - redis
      - market-data-api

  portfolio-worker:
    build: ./apps/portfolio-worker
    env_file:
      - .env
    environment:
      MARKET_DATA_BASE_URL: http://market-data-api:8010
    depends_on:
      - db
      - redis
      - market-data-api

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

## 17. Implementation Roadmap

### Phase 1: Portfolio API Without Market Providers

- Users, portfolios, instruments tables (portfolio schema).
- Manual transactions.
- Current positions view.
- Basic REST API (CRUD).
- Docker Compose setup (portfolio-api + db + redis).

**Goal:** Manually enter holdings and see current positions.

### Phase 2: Connect to Market Data API

- `MarketDataClient` inside Portfolio API.
- Batch quote lookup for allocation.
- Allocation calculation using Market Data API prices.
- Staleness warnings in frontend responses.

**Goal:** Portfolio allocation is calculated using data from the separate Market Data API.

### Phase 3: Risk Analytics

- Daily returns calculation.
- Annualized volatility, beta, max drawdown.
- Correlation matrix.
- Historical VaR, Sharpe ratio.
- Portfolio snapshots.

**Goal:** Portfolio risk calculations use historical data from Market Data API.

### Phase 4: Watchlists & Scenarios

- Watchlist tables + APIs.
- Scenario tables + APIs.
- Scenario analysis endpoint.
- Current vs scenario comparison.

**Goal:** Preview buying, selling, or rebalancing before making trades.

### Phase 5: Strength Scoring & Fundamentals

- Metric definitions + metric snapshots.
- Normalized metric scoring.
- Portfolio strength score.
- ETF holdings for look-through analysis (later).

**Goal:** Compare portfolio quality using a consistent scoring model.

---

## 18. Ingestion Triggers

### 18.1 When a Ticker Is Added to a Portfolio

```text
Portfolio API:
1. Create or find instrument in portfolio.instruments.
2. Extract symbol + exchange.
3. Call Market Data API: POST /v1/refresh
   {symbols: ["NVDA"], data_types: ["latest_price", "daily_history"]}
4. Market Data API queues fetch jobs internally.

Market Data API (async):
5. Resolve provider symbols via provider_symbol_mappings.
6. Fetch from providers.
7. Normalize and store in price_bars / quote_snapshots / latest_price_cache.
8. Mark fetch jobs as complete.
```

### 18.2 When a Ticker Is Added to a Watchlist

```text
Portfolio API:
1. Create or find instrument.
2. Call Market Data API: POST /v1/refresh
   {symbols: ["IONQ"], data_types: ["latest_price", "daily_history"]}
```

### 18.3 When a Ticker Is Searched

```text
Portfolio API:
1. Check local portfolio.instruments first.
2. If not found, call Market Data API: GET /v1/symbols/search?query=nvda
3. Save lookup result locally in portfolio.instruments.
4. Do NOT trigger full history fetch until user adds to portfolio or watchlist.
```

---

## 19. Authentication

For local single-user, the Portfolio API starts with no external auth or a static API token. A `users` table exists for future expansion.

Between services: static `MARKET_DATA_INTERNAL_API_KEY` via Bearer token header.

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
