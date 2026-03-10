"""Celery application instance and beat schedule for the AI Trend Monitor.

Configures the Celery broker/backend from application settings, sets
sensible serialisation and reliability defaults, and defines the periodic
beat schedule for data collection, analytics, and report generation.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_trend_monitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # -- Serialisation -----------------------------------------------------
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # -- Timezone ----------------------------------------------------------
    timezone="UTC",
    enable_utc=True,

    # -- Reliability -------------------------------------------------------
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # -- Result backend ----------------------------------------------------
    result_expires=60 * 60 * 24,  # 24 hours

    # -- Task routing (optional, can be extended) --------------------------
    task_default_queue="default",
)

# ---------------------------------------------------------------------------
# Beat schedule
# ---------------------------------------------------------------------------

collection_hours: int = settings.COLLECTION_SCHEDULE_HOURS
analytics_hours: int = settings.ANALYTICS_SCHEDULE_HOURS

celery_app.conf.beat_schedule = {
    # Collect data from all sources every N hours.
    "collect-all-sources": {
        "task": "app.tasks.collection_tasks.collect_all_task",
        "schedule": crontab(minute=0, hour=f"*/{collection_hours}"),
        "options": {"queue": "default"},
    },
    # Run analytics (growth rates, signals, niche assignment) 30 minutes
    # after each collection run.
    "run-analytics": {
        "task": "app.tasks.analytics_tasks.run_analytics_task",
        "schedule": crontab(minute=30, hour=f"*/{collection_hours}"),
        "options": {"queue": "default"},
    },
    # Generate a daily report every morning at 08:00 UTC.
    "generate-daily-report": {
        "task": "app.tasks.analytics_tasks.generate_daily_report_task",
        "schedule": crontab(minute=0, hour=8),
        "options": {"queue": "default"},
    },
    # Generate a weekly report every Monday at 08:00 UTC.
    "generate-weekly-report": {
        "task": "app.tasks.analytics_tasks.generate_weekly_report_task",
        "schedule": crontab(minute=0, hour=8, day_of_week=1),
        "options": {"queue": "default"},
    },
}
