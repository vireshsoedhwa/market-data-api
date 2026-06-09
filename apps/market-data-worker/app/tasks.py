"""
Market Data Worker tasks.

TODO: Implement tasks for:
  - fetch_latest_quotes(symbols)
  - fetch_daily_bars(symbol, start_date, end_date)
  - refresh_stale_data()
  - backfill_history(symbol, start_date, end_date)
  - provider_health_check()
"""

from app.celery_app import celery_app


@celery_app.task(name="market_data.ping")
def ping():
    return "pong"
