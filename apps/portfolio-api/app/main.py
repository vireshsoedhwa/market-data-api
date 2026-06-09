"""
Portfolio Tracker API — placeholder.

This service will own portfolios, transactions, watchlists, scenarios,
analytics, and risk calculations. It calls the Market Data API over HTTP
for all market data needs.

See portfolio_tracker_v1.md for the full specification.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Portfolio Tracker API",
    description="Personal stock portfolio and exploration dashboard backend.",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "portfolio-api", "version": "0.1.0"}
