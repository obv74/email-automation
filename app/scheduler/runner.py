"""APScheduler setup."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.scheduler.jobs import run_followup_check_all, run_gmail_poll_sync, run_reminder_check_all

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
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
        id="gmail_poll",
        replace_existing=True,
    )
    _scheduler.add_job(
        run_reminder_check_all,
        "interval",
        minutes=settings.reminder_check_interval_minutes,
        id="reminder_check",
        replace_existing=True,
    )
    _scheduler.add_job(
        run_followup_check_all,
        "interval",
        minutes=settings.followup_check_interval_minutes,
        id="followup_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started (all active companies)")
