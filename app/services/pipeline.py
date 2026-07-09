"""Core pipeline: Gmail thread → extract → price → reply → log."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MessageLog, ProcessedThread
from app.extraction.llm import extract_job_from_thread
from app.gmail.client import get_gmail_service
from app.gmail.drafts import create_draft, send_message
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids, mark_thread_as_read
from app.pricing.quote import compute_quote
from app.pricing.sheets import fetch_pricing_rows
from app.replies.generate import generate_reply

logger = logging.getLogger(__name__)

PROCESSING_STALE_MINUTES = 20


def _should_skip_thread(
    existing: Optional[ProcessedThread],
    latest_message_id: str,
    force: bool,
) -> Optional[str]:
    if force:
        return None
    if not existing:
        return None
    if existing.last_message_id != latest_message_id:
        return None  # new reply in thread — reprocess
    if existing.status == "processed":
        return "already processed"
    if existing.status == "processing":
        age = datetime.utcnow() - existing.processed_at
        if age < timedelta(minutes=PROCESSING_STALE_MINUTES):
            return "already processing"
    return None


def _claim_thread(db: Session, tenant_id: str, thread_id: str, message_id: str) -> ProcessedThread:
    """Lock thread in DB before slow Ollama call — prevents duplicate drafts on poll overlap."""
    existing = (
        db.query(ProcessedThread)
        .filter(
            ProcessedThread.tenant_id == tenant_id,
            ProcessedThread.gmail_thread_id == thread_id,
        )
        .first()
    )
    if existing:
        existing.last_message_id = message_id
        existing.status = "processing"
        existing.processed_at = datetime.utcnow()
        row = existing
    else:
        row = ProcessedThread(
            tenant_id=tenant_id,
            gmail_thread_id=thread_id,
            last_message_id=message_id,
            status="processing",
        )
        db.add(row)
    db.commit()
    return row


def _release_thread_claim(db: Session, row: ProcessedThread, success: bool) -> None:
    if success:
        row.status = "processed"
        row.processed_at = datetime.utcnow()
    else:
        row.status = "failed"
    db.commit()


async def process_thread(db: Session, tenant_id: str, thread_id: str, force: bool = False) -> dict:
    gmail = get_gmail_service(db, tenant_id)
    messages, conversation = fetch_full_thread(gmail, thread_id)
    if not messages:
        return {"status": "empty", "thread_id": thread_id}

    latest = messages[-1]
    existing = (
        db.query(ProcessedThread)
        .filter(
            ProcessedThread.tenant_id == tenant_id,
            ProcessedThread.gmail_thread_id == thread_id,
        )
        .first()
    )
    skip_reason = _should_skip_thread(existing, latest.message_id, force)
    if skip_reason:
        return {"status": "skipped", "thread_id": thread_id, "reason": skip_reason}

    claim = _claim_thread(db, tenant_id, thread_id, latest.message_id)

    try:
        job = await extract_job_from_thread(conversation)
        pricing_rows = fetch_pricing_rows(db, tenant_id)
        quote = compute_quote(job, pricing_rows)
        rule_name, reply_body = generate_reply(job, quote)

        subject = latest.subject if latest.subject.lower().startswith("re:") else f"Re: {latest.subject}"
        to_email = job.customer_email or latest.from_email

        settings = get_settings()
        draft_id = None
        message_id = None
        direction = "draft"

        if settings.reply_mode == "send":
            sent = send_message(gmail, to_email, subject, reply_body, thread_id)
            message_id = sent.get("id")
            direction = "outbound"
        else:
            draft = create_draft(gmail, to_email, subject, reply_body, thread_id)
            draft_id = draft.get("id")
            direction = "draft"

        log = MessageLog(
            tenant_id=tenant_id,
            gmail_thread_id=thread_id,
            gmail_message_id=message_id,
            gmail_draft_id=draft_id,
            direction=direction,
            subject=subject,
            extraction_json=json.dumps(job.model_dump()),
            quote_amount=quote,
            reply_body=reply_body,
            rule_name=rule_name,
        )
        db.add(log)
        _release_thread_claim(db, claim, success=True)

        try:
            mark_thread_as_read(gmail, thread_id)
        except Exception as exc:
            logger.warning("Could not mark thread read %s: %s", thread_id, exc)

        return {
            "status": "ok",
            "thread_id": thread_id,
            "extraction": job.model_dump(),
            "quote": quote,
            "rule": rule_name,
            "direction": direction,
            "draft_id": draft_id,
            "message_id": message_id,
        }
    except Exception:
        _release_thread_claim(db, claim, success=False)
        raise


async def poll_unread_threads(db: Session, tenant_id: str) -> list[dict]:
    gmail = get_gmail_service(db, tenant_id)
    thread_ids = list_recent_thread_ids(gmail, query="is:unread", max_results=10)
    results = []
    for tid in thread_ids:
        try:
            result = await process_thread(db, tenant_id, tid)
            results.append(result)
        except Exception as exc:
            logger.exception("Failed processing thread %s: %s", tid, exc)
            results.append({"status": "error", "thread_id": tid, "error": str(exc)})
    return results
