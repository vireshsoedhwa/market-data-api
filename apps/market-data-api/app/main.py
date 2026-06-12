from fastapi import FastAPI

from app.errors import register_error_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import health, history, providers, quotes, refresh, symbols
from app.routes import (
    v2_capabilities,
    v2_history,
    v2_providers,
    v2_quotes,
    v2_refresh,
    v2_symbols,
)

app = FastAPI(
    title="Market Data API",
    description="Standalone market data acquisition, normalization, and caching service.",
    version="2.0.0",
)

# --- Middleware (order matters: outermost first) ---
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# --- Error handlers ---
register_error_handlers(app)

# --- V1 routes (deprecated, kept as aliases) ---
app.include_router(health.router)
app.include_router(quotes.router)
app.include_router(history.router)
app.include_router(refresh.router)
app.include_router(symbols.router)
app.include_router(providers.router)

# --- V2 routes ---
app.include_router(v2_capabilities.router)
app.include_router(v2_quotes.router)
app.include_router(v2_history.router)
app.include_router(v2_refresh.router)
app.include_router(v2_symbols.router)
app.include_router(v2_providers.router)
