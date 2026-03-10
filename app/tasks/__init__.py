"""Celery task definitions for the AI Trend Monitor.

Re-exports the Celery application instance so that worker processes can
discover it via ``celery -A app.tasks worker``.
"""

from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
