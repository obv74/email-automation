"""Core pipeline: Gmail thread → extract → price → reply → log."""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MessageLog, ProcessedThread
from app.extraction.llm import extract_job_from_thread
from app.gmail.client import get_gmail_service
from app.gmail.drafts import create_draft, send_message
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids
from app.pricing.quote import compute_quote
from app.pricing.sheets import fetch_pricing_rows
from app.replies.generate import generate_reply

logger = logging.getLogger(__name__)


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
    if existing and existing.last_message_id == latest.message_id and not force:
        return {"status": "skipped", "thread_id": thread_id, "reason": "already processed"}

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

    if existing:
        existing.last_message_id = latest.message_id
        existing.status = "processed"
    else:
        db.add(
            ProcessedThread(
                tenant_id=tenant_id,
                gmail_thread_id=thread_id,
                last_message_id=latest.message_id,
                status="processed",
            )
        )
    db.commit()

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
