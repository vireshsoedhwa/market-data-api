"""
Portfolio Worker — placeholder.

TODO: Implement Celery app for portfolio snapshot recalculation,
      risk metric computation, and allocation snapshots.
"""

import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "portfolio_worker",
    broker=redis_url,
    backend=redis_url,
)

celery_app.autodiscover_tasks(["app.tasks"])
