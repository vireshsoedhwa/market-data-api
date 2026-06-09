"""
Portfolio Worker tasks — placeholder.

TODO: Implement tasks for:
  - recalculate_portfolio_snapshots(portfolio_id)
  - recalculate_risk_metrics(portfolio_id)
  - compute_allocation_snapshots(portfolio_id)
  - run_scenario_comparison(scenario_id)
"""

from app.celery_app import celery_app


@celery_app.task(name="portfolio.ping")
def ping():
    return "pong"
