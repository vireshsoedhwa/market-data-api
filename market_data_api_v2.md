# Market Data API v2 — Agent-First Design

## Vision

The market-data-api becomes the **sole backend service** in this stack. Instead of a separate portfolio-api and portfolio-worker, AI agents interact directly with the market-data-api as a tool/datasource. The API is designed so that any LLM-based agent (GPT, Claude, LangChain, CrewAI, custom) can discover, query, and act on market data autonomously.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  AI Agent (LLM tool-use, MCP client, or raw HTTP)   │
└──────────────────────────┬──────────────────────────┘
                           │ HTTP / MCP
                           ▼
┌─────────────────────────────────────────────────────┐
│              market-data-api (FastAPI)               │
│                                                     │
│  ┌─────────────┐ ┌────────────┐ ┌───────────────┐  │
│  │ Tool Layer  │ │ Data Layer │ │  Discovery /  │  │
│  │ (endpoints  │ │ (quotes,   │ │  Capabilities │  │
│  │  as tools)  │ │  history,  │ │               │  │
│  │             │ │  search)   │ │               │  │
│  └─────────────┘ └────────────┘ └───────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ Provider Router (Finnhub, Massive, etc.)     │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐    │
│  │  Redis   │  │ TimescaleDB│  │ Celery Worker│    │
│  │  (cache) │  │ (storage)  │  │ (async jobs) │    │
│  └──────────┘  └────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## Design Principles

1. **Discoverable** — agents learn what the API can do at runtime, not from docs
2. **Deterministic** — identical inputs always produce identical response shapes
3. **Self-describing** — every response includes metadata about freshness, confidence, and lineage
4. **Batch-native** — agents often need N symbols; batch is first-class, not an afterthought
5. **Fault-transparent** — partial failures are surfaced clearly, never silently swallowed
6. **Stateless for reads, explicit for writes** — no hidden session state

---

## Endpoint Plan

### Discovery & Capabilities

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v2/capabilities` | What the API can do: endpoints, limits, supported exchanges, timeframes, data freshness guarantees |
| GET | `/v2/openapi.json` | Full OpenAPI 3.1 spec with rich descriptions + examples (agent-consumable) |
| GET | `/v2/tools` | Tool-calling schema (OpenAI function-calling format + MCP tool definitions) |
| GET | `/health` | Liveness check (unchanged) |

### Market Data (Read)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v2/quotes/{symbol}` | Latest price for a single symbol |
| POST | `/v2/quotes/batch` | Latest prices for multiple symbols |
| GET | `/v2/history/{symbol}` | OHLCV bars for a date range (paginated) |
| POST | `/v2/history/batch` | History for multiple symbols |
| GET | `/v2/symbols/search` | Fuzzy symbol search |
| GET | `/v2/symbols/{symbol}/metadata` | Fundamentals / metadata for a symbol |

### Agent Actions (Write)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v2/refresh` | Request fresh data pull (idempotent with `Idempotency-Key`) |
| GET | `/v2/jobs/{job_id}` | Poll async job status |

### Provider Introspection

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v2/providers/status` | Health and capability of each provider |

---

## Key Changes from v1

### 1. Capabilities Endpoint (`GET /v2/capabilities`)

Returns a machine-readable manifest:

```json
{
  "version": "2.0.0",
  "endpoints": ["quotes", "history", "symbols", "refresh"],
  "max_batch_size": 50,
  "supported_timeframes": ["1d", "1wk", "1mo"],
  "supported_exchanges": ["NYSE", "NASDAQ", "TSX"],
  "data_freshness": {
    "latest_price": {"typical_delay": "15min", "max_staleness": "24h"},
    "daily_history": {"coverage_target": 0.95, "lag": "EOD"}
  },
  "rate_limits": {
    "requests_per_minute": 120,
    "batch_max_symbols": 50
  },
  "authentication": {
    "type": "bearer",
    "header": "Authorization"
  }
}
```

### 2. Tool Definitions Endpoint (`GET /v2/tools`)

Returns tool schemas in OpenAI function-calling format so agents can auto-register:

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_latest_price",
        "description": "Get the most recent price for a stock symbol",
        "parameters": {
          "type": "object",
          "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol (e.g. AAPL)"},
            "exchange": {"type": "string", "description": "Optional exchange filter"}
          },
          "required": ["symbol"]
        }
      }
    }
  ]
}
```

### 3. Structured Error Envelope

All errors use a consistent shape:

```json
{
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "No data available for symbol XYZ",
    "symbol": "XYZ",
    "retry_after_seconds": null
  }
}
```

Standard error codes: `SYMBOL_NOT_FOUND`, `PROVIDER_EXHAUSTED`, `RATE_LIMITED`, `INVALID_DATE_RANGE`, `INTERNAL_ERROR`

### 4. Response Envelope with Request Echo

Every successful response wraps data in:

```json
{
  "request": {"symbol": "AAPL", "endpoint": "quotes"},
  "data": { ... },
  "meta": {
    "provider": "finnhub",
    "source_type": "cache",
    "confidence": "high",
    "as_of": "2026-06-09T18:30:00Z",
    "is_delayed": true,
    "delay_minutes": 15,
    "warnings": []
  }
}
```

### 5. Rate-Limit Headers

Every response includes:
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 117
X-RateLimit-Reset: 1749523860
```

### 6. Pagination on History

```
GET /v2/history/AAPL?start_date=2020-01-01&end_date=2026-06-09&limit=252&cursor=...
```

Response includes `next_cursor` if more data available.

### 7. Idempotent Refresh

```
POST /v2/refresh
Idempotency-Key: agent-run-abc123

→ Returns same job_id if called again with same key within 24h
```

### 8. Content Negotiation

```
Accept: application/json  (default)
Accept: text/csv          (for history endpoint — pandas-friendly)
```

---

## MCP (Model Context Protocol) Support — Future Phase

Expose the same functionality as an MCP server so agents using the MCP standard can connect directly:

- **Resources**: `market://symbols/{symbol}/price`, `market://symbols/{symbol}/history`
- **Tools**: `get_latest_price`, `get_daily_history`, `search_symbols`, `refresh_data`
- **Prompts**: Pre-built prompt templates for common analysis patterns

This can be a thin adapter layer on top of the same FastAPI service.

---

## Implementation Phases

### Phase 1 — Foundation (current sprint)
- [ ] Add `/v2/capabilities` endpoint
- [ ] Add `/v2/tools` endpoint (OpenAI function-calling format)
- [ ] Implement structured error envelope + error codes
- [ ] Add response wrapper with `request` echo + `meta` block
- [ ] Rate-limit middleware with headers
- [ ] Migrate existing v1 routes to v2 format (keep v1 as deprecated alias)

### Phase 2 — Enhanced Data
- [ ] Pagination (cursor-based) on history
- [ ] Idempotency on refresh endpoint
- [ ] CSV content negotiation for history
- [ ] Richer OpenAPI descriptions + request/response examples on every endpoint
- [ ] Symbol search actually backed by providers

### Phase 3 — MCP Adapter
- [ ] MCP server wrapper (stdio or SSE transport)
- [ ] Resource definitions for prices and history
- [ ] Tool definitions matching v2 endpoints
- [ ] Integration tests with a reference MCP client

---

## Docker Compose (Simplified)

```yaml
services:
  db:         # TimescaleDB — unchanged
  redis:      # Redis — unchanged
  market-data-api:    # FastAPI — the only user-facing service
  market-data-worker: # Celery — async refresh jobs
```

No portfolio-api, no portfolio-worker. Agents consume market-data-api directly.

---

## Authentication Strategy

- **Bearer token** for direct HTTP access (unchanged)
- **MCP auth** via environment variable injection (MCP clients pass credentials at connection time)
- Future: scoped API keys with per-key rate limits for multi-agent deployments

---

## Success Criteria

An AI agent should be able to:
1. `GET /v2/capabilities` → learn what's available
2. `GET /v2/tools` → register tools in its function-calling runtime
3. `GET /v2/quotes/AAPL` → get a price with full metadata
4. Interpret `confidence: "low"` → decide to call `POST /v2/refresh` first
5. Handle `error.code: "RATE_LIMITED"` → back off using `retry_after_seconds`
6. All without reading any human documentation