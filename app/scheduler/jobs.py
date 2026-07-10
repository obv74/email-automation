"""Scheduled jobs: Gmail poll, reminders, follow-ups."""

import asyncio
import logging
from datetime import date, datetime, timedelta

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import FollowupLog, MessageLog, ProcessedThread, ReminderLog, ScheduledJobRecord, SessionLocal
from app.tenants.service import get_tenant, tenant_pricing_sheet_id, tenant_reply_mode
from app.gmail.client import get_gmail_service
from app.gmail.drafts import create_draft, send_message
from app.services.pipeline import poll_unread_threads

logger = logging.getLogger(__name__)


def _send_email(db: Session, tenant_id: str, to: str, subject: str, body: str, direction: str) -> None:
    tenant = get_tenant(db, tenant_id)
    reply_mode = tenant_reply_mode(tenant) if tenant else get_settings().reply_mode
    gmail = get_gmail_service(db, tenant_id)
    draft_id = None
    message_id = None
    if reply_mode == "send":
        sent = send_message(gmail, to, subject, body)
        message_id = sent.get("id")
    else:
        draft = create_draft(gmail, to, subject, body)
        draft_id = draft.get("id")

    db.add(
        MessageLog(
            tenant_id=tenant_id,
            gmail_message_id=message_id,
            gmail_draft_id=draft_id,
            direction=direction,
            subject=subject,
            reply_body=body,
        )
    )
    db.commit()


def sync_jobs_from_sheet(db: Session, tenant_id: str) -> int:
    """Import booked jobs from a 'Jobs' tab on the pricing sheet.

    The Jobs tab is optional — missing tab / bad range must not crash the scheduler.
    """
    tenant = get_tenant(db, tenant_id)
    sheet_id = tenant_pricing_sheet_id(tenant) if tenant else get_settings().pricing_sheet_id
    if not sheet_id:
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from app.auth.google_oauth import load_credentials

    creds = load_credentials(db, tenant_id)
    if not creds:
        return 0

    try:
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="Jobs!A:F")
            .execute()
        )
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        # 400 Unable to parse range = tab "Jobs" does not exist (optional)
        logger.info(
            "Jobs tab not available for tenant %s (sheet %s): %s",
            tenant_id,
            sheet_id,
            exc,
        )
        if status not in (400, 403, 404):
            logger.warning("Unexpected Sheets error syncing Jobs for %s: %s", tenant_id, exc)
        return 0
    except Exception as exc:
        logger.warning("Could not sync Jobs sheet for %s: %s", tenant_id, exc)
        return 0

    values = result.get("values", [])
    if len(values) < 2:
        return 0

    headers = [h.strip().lower().replace(" ", "_") for h in values[0]]
    count = 0
    for idx, row in enumerate(values[1:], start=2):
        item = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        external_id = str(item.get("job_id", f"row-{idx}"))
        email = item.get("customer_email", "")
        if not email:
            continue

        existing = (
            db.query(ScheduledJobRecord)
            .filter(
                ScheduledJobRecord.tenant_id == tenant_id,
                ScheduledJobRecord.external_id == external_id,
            )
            .first()
        )
        if existing:
            existing.move_date = item.get("move_date") or existing.move_date
            existing.customer_name = item.get("customer_name") or existing.customer_name
            existing.job_description = item.get("description") or existing.job_description
            existing.load_address = item.get("load_address") or existing.load_address
        else:
            db.add(
                ScheduledJobRecord(
                    tenant_id=tenant_id,
                    external_id=external_id,
                    source="sheet",
                    customer_email=email,
                    customer_name=item.get("customer_name"),
                    move_date=item.get("move_date"),
                    job_description=item.get("description"),
                    load_address=item.get("load_address"),
                )
            )
            count += 1
    db.commit()
    return count


def run_reminder_check(tenant_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        sync_jobs_from_sheet(db, tenant_id)
        today = date.today()
        jobs = db.query(ScheduledJobRecord).filter(ScheduledJobRecord.tenant_id == tenant_id).all()

        for job in jobs:
            if not job.move_date or not job.customer_email:
                continue
            try:
                move_day = date_parser.parse(job.move_date).date()
            except (ValueError, TypeError):
                continue

            for days_before in settings.reminder_day_list:
                target = move_day - timedelta(days=days_before)
                if target != today:
                    continue

                sent = (
                    db.query(ReminderLog)
                    .filter(
                        ReminderLog.tenant_id == tenant_id,
                        ReminderLog.job_id == job.id,
                        ReminderLog.days_before == days_before,
                    )
                    .first()
                )
                if sent:
                    continue

                subject = f"Move reminder — {days_before} day(s) out"
                body = (
                    f"Hi {job.customer_name or 'there'},\n\n"
                    f"This is a reminder that your move is scheduled for {job.move_date}.\n"
                    f"Load address: {job.load_address or 'See prior confirmation'}\n"
                    f"Details: {job.job_description or 'N/A'}\n\n"
                    f"Reply if anything changed.\n\nThank you!"
                )
                _send_email(db, tenant_id, job.customer_email, subject, body, "reminder")
                db.add(
                    ReminderLog(
                        tenant_id=tenant_id,
                        job_id=job.id,
                        days_before=days_before,
                    )
                )
                db.commit()
    finally:
        db.close()


def run_followup_check(tenant_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=settings.followup_wait_days)
        awaiting = (
            db.query(ProcessedThread)
            .filter(
                ProcessedThread.tenant_id == tenant_id,
                ProcessedThread.status == "awaiting_reply",
                ProcessedThread.processed_at <= cutoff,
            )
            .all()
        )

        for thread in awaiting:
            attempts = (
                db.query(FollowupLog)
                .filter(
                    FollowupLog.tenant_id == tenant_id,
                    FollowupLog.gmail_thread_id == thread.gmail_thread_id,
                )
                .count()
            )
            if attempts >= settings.followup_max_attempts:
                continue

            last_outbound = (
                db.query(MessageLog)
                .filter(
                    MessageLog.tenant_id == tenant_id,
                    MessageLog.gmail_thread_id == thread.gmail_thread_id,
                    MessageLog.direction.in_(["outbound", "draft", "followup"]),
                )
                .order_by(MessageLog.created_at.desc())
                .first()
            )
            if not last_outbound or not last_outbound.reply_body:
                continue

            subject = last_outbound.subject or "Following up on your move request"
            to = ""
            if last_outbound.extraction_json:
                import json

                data = json.loads(last_outbound.extraction_json)
                to = data.get("customer_email") or ""
            if not to:
                logger.warning("Follow-up skipped: no customer email for thread %s", thread.gmail_thread_id)
                continue

            _send_email(
                db,
                tenant_id,
                to,
                subject,
                last_outbound.reply_body,
                "followup",
            )
            db.add(
                FollowupLog(
                    tenant_id=tenant_id,
                    gmail_thread_id=thread.gmail_thread_id,
                    attempt=attempts + 1,
                )
            )
            db.commit()
    finally:
        db.close()


def run_gmail_poll_sync(_unused: str = "") -> None:
    asyncio.run(run_gmail_poll_all())


async def run_gmail_poll_all() -> None:
    db = SessionLocal()
    try:
        from app.tenants.service import list_pollable_tenants, tenant_due_for_poll

        for tenant in list_pollable_tenants(db):
            if not tenant_due_for_poll(tenant):
                continue
            try:
                await poll_unread_threads(db, tenant.id)
            except Exception as exc:
                logger.exception("Gmail poll failed for %s: %s", tenant.slug, exc)
    finally:
        db.close()


def run_reminder_check_all(_unused: str = "") -> None:
    db = SessionLocal()
    try:
        from app.tenants.service import list_pollable_tenants

        for tenant in list_pollable_tenants(db):
            try:
                run_reminder_check(tenant.id)
            except Exception as exc:
                logger.exception("Reminder check failed for %s: %s", tenant.slug, exc)
    finally:
        db.close()


def run_followup_check_all(_unused: str = "") -> None:
    db = SessionLocal()
    try:
        from app.tenants.service import list_pollable_tenants

        for tenant in list_pollable_tenants(db):
            try:
                run_followup_check(tenant.id)
            except Exception as exc:
                logger.exception("Follow-up check failed for %s: %s", tenant.slug, exc)
    finally:
        db.close()
