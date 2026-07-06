"""APScheduler setup."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.scheduler.jobs import run_followup_check, run_gmail_poll_sync, run_reminder_check

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler(tenant_id: str) -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled")
        return
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_gmail_poll_sync,
        "interval",
        minutes=settings.poll_gmail_interval_minutes,
        args=[tenant_id],
        id="gmail_poll",
        replace_existing=True,
    )
    _scheduler.add_job(
        run_reminder_check,
        "interval",
        minutes=settings.reminder_check_interval_minutes,
        args=[tenant_id],
        id="reminder_check",
        replace_existing=True,
    )
    _scheduler.add_job(
        run_followup_check,
        "interval",
        minutes=settings.followup_check_interval_minutes,
        args=[tenant_id],
        id="followup_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started")
