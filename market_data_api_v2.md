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
7. **Secure by default** — all endpoints require authentication, inputs are strictly validated, internal details are never leaked to unauthenticated callers

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
- [ ] Require auth on all endpoints except `/health`
- [ ] Input validation middleware (symbol regex, date range checks, batch size cap)
- [ ] Strip framework-identifying response headers

### Phase 2 — Enhanced Data
- [ ] Pagination (cursor-based) on history with signed cursor tokens
- [ ] Idempotency on refresh endpoint with key format validation
- [ ] CSV content negotiation for history
- [ ] Richer OpenAPI descriptions + request/response examples on every endpoint
- [ ] Symbol search actually backed by providers
- [ ] Scoped API keys (`read` / `read-write`) with per-key rate limits in Redis
- [ ] Per-key daily refresh quota enforcement
- [ ] Omit `meta.provider` for non-admin keys

### Phase 3 — MCP Adapter
- [ ] MCP server wrapper (stdio or SSE transport)
- [ ] Resource definitions for prices and history
- [ ] Tool definitions matching v2 endpoints (static definitions only — no dynamic content)
- [ ] MCP auth — validate bearer token through shared auth middleware
- [ ] MCP resource URI validation (same rules as REST path params)
- [ ] Integration tests with a reference MCP client
- [ ] Verify MCP requests flow through unified rate-limit middleware

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

## Authentication & Authorization Strategy

- **Bearer token** for direct HTTP access — validated server-side on every request (unchanged mechanism, but now required on all endpoints except `/health`)
- **Scoped API keys** — each key carries a scope (`read` or `read-write`); `read` keys cannot call `POST /v2/refresh`
- **Per-key rate limits** — each API key has its own quota tracked in Redis; exhaustion returns `429` with `Retry-After`
- **MCP auth** — MCP clients pass a bearer token at SSE connection time; the MCP adapter validates it through the same auth middleware as HTTP
- **Key rotation** — API keys support non-disruptive rotation (old key valid for a grace period after new key is issued)

---

## Security Considerations

### Transport

- **TLS required** — the API must only be served over HTTPS when publicly exposed; HTTP listeners should redirect or refuse
- **CORS** — strict `Access-Control-Allow-Origin`; default deny, allowlist specific origins if browser-based MCP clients are supported
- **SSE transport** — same TLS and auth requirements as REST; no unauthenticated SSE connections

### Input Validation

- **Symbol parameters** — strict regex validation (`^[A-Z0-9.\-]{1,10}$`); reject anything else with `400`
- **Date parameters** — validate format and range (no future dates beyond T+1, no ranges exceeding provider limits)
- **Batch size** — enforce `max_batch_size` server-side; never trust client-supplied counts
- **Cursor / pagination tokens** — signed or opaque tokens; reject tampered values
- **`Idempotency-Key`** — length-limited, alphanumeric+hyphen only

### Information Disclosure

- **Discovery endpoints** (`/v2/capabilities`, `/v2/tools`, `/v2/providers/status`) require authentication; unauthenticated requests get `401`, not a reduced payload
- **Error responses** — never include stack traces, SQL fragments, or internal hostnames; use only the defined error codes
- **Response metadata** — the `meta.provider` field is omitted for public-scoped keys; only admin-scoped keys see provider attribution
- **Headers** — strip `Server`, `X-Powered-By`, and other framework-identifying headers

### Rate Limiting & Abuse Prevention

- **Unified enforcement** — both HTTP and MCP requests pass through the same rate-limit middleware; the MCP adapter must not bypass it
- **Batch amplification** — a single batch request counts as N requests against the rate limit (where N = number of symbols)
- **Refresh quota** — `POST /v2/refresh` has a separate per-key daily cap (e.g., 50/day) to prevent job-queue flooding
- **Slowloris / connection exhaustion** — configure request timeouts and max concurrent connections at the reverse proxy layer

### MCP-Specific

- **Tool definitions are static** — never include dynamic or user-supplied content in MCP tool `name` or `description` fields to prevent prompt injection
- **Resource URI validation** — `market://` URIs are parsed and validated identically to REST path parameters; no path traversal
- **No implicit trust** — MCP clients are treated as untrusted; every tool invocation is individually authorized against the key's scope

### Dependency & Infrastructure

- **Secrets management** — API keys, DB credentials, and provider tokens stored in environment variables or a secrets manager; never in code or config files committed to git
- **Redis ACLs** — the Redis instance should use a dedicated user with restricted command set (no `FLUSHALL`, `CONFIG`, `DEBUG`)
- **Database** — parameterized queries only (SQLAlchemy handles this); connection pooling with max-connection limits
- **Container hardening** — run as non-root, read-only filesystem where possible, no unnecessary capabilities

---

## Success Criteria

An AI agent should be able to:
1. `GET /v2/capabilities` → learn what's available
2. `GET /v2/tools` → register tools in its function-calling runtime
3. `GET /v2/quotes/AAPL` → get a price with full metadata
4. Interpret `confidence: "low"` → decide to call `POST /v2/refresh` first
5. Handle `error.code: "RATE_LIMITED"` → back off using `retry_after_seconds`
6. All without reading any human documentation