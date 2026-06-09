from fastapi import FastAPI

from app.routes import health, history, providers, quotes, refresh, symbols

app = FastAPI(
    title="Market Data API",
    description="Standalone market data acquisition, normalization, and caching service.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(quotes.router)
app.include_router(history.router)
app.include_router(refresh.router)
app.include_router(symbols.router)
app.include_router(providers.router)
