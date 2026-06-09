-- =============================================================================
-- Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- =============================================================================
-- Market Data Schema
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS market_data;

-- 16.1 Provider Symbol Mappings
CREATE TABLE market_data.provider_symbol_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    exchange TEXT,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(symbol, exchange, provider)
);

-- 16.2 Price Bars
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

SELECT create_hypertable('market_data.price_bars', 'ts', if_not_exists => TRUE);

-- 16.3 Quote Snapshots
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

-- 16.4 Latest Price Cache
CREATE TABLE market_data.latest_price_cache (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT '',

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

-- 16.5 API Cache Entries
CREATE TABLE market_data.api_cache_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- 16.6 Market Data Fetch Jobs
CREATE TABLE market_data.market_data_fetch_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    symbol TEXT,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    raw_response JSONB
);

-- 16.7 Market Data Providers
CREATE TABLE market_data.market_data_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- 16.8 Provider Credentials
CREATE TABLE market_data.market_data_provider_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES market_data.market_data_providers(id),

    credential_name TEXT NOT NULL,
    env_var_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(provider_id, credential_name)
);

-- 16.9 Provider Rate Limit Rules
CREATE TABLE market_data.provider_rate_limit_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES market_data.market_data_providers(id),

    rule_name TEXT NOT NULL,
    max_requests INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,

    applies_to_endpoint TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 16.10 Provider Request Log
CREATE TABLE market_data.provider_request_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- 16.11 Provider Health State
CREATE TABLE market_data.provider_health_state (
    provider_id UUID PRIMARY KEY REFERENCES market_data.market_data_providers(id),

    status TEXT NOT NULL DEFAULT 'healthy',
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    disabled_until TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Seed: Default Providers
-- =============================================================================

INSERT INTO market_data.market_data_providers (name, display_name, supports_latest_price, supports_daily_history, base_url)
VALUES
    ('alpaca',        'Alpaca',          true,  false, 'https://data.alpaca.markets'),
    ('finnhub',       'Finnhub',         true,  false, 'https://finnhub.io/api'),
    ('twelvedata',    'Twelve Data',     true,  true,  'https://api.twelvedata.com'),
    ('stockdata',     'StockData.org',   true,  false, 'https://api.stockdata.org'),
    ('tiingo',        'Tiingo',          false, true,  'https://api.tiingo.com'),
    ('alpha_vantage', 'Alpha Vantage',   false, true,  'https://www.alphavantage.co'),
    ('fmp',           'Financial Modeling Prep', false, true, 'https://financialmodelingprep.com/api'),
    ('stooq',         'Stooq',           false, true,  'https://stooq.com/q/d/l/')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Portfolio Schema (placeholder — tables created when portfolio-api is built)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS portfolio;
