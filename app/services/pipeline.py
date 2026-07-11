"""Core pipeline: Gmail thread → classify → extract → (optional) reply → log."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MessageLog, ProcessedThread
from app.extraction.enrich import enrich_job_for_pricing
from app.extraction.llm import classify_email, extract_job_from_thread
from app.extraction.schema import ExtractedJob
from app.gmail.client import get_gmail_service
from app.gmail.drafts import create_draft, send_message
from app.gmail.labels import (
    LABEL_DRAFTED,
    LABEL_EXTRACTED,
    LABEL_IGNORED,
    LABEL_NEEDS_HUMAN,
    apply_agent_label,
)
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids
from app.pricing.quote import compute_quote, quote_failure_reason
from app.pricing.sheets import append_extracted_job, fetch_pricing_rows, fetch_stock_responses
from app.replies.generate import generate_reply
from app.tenants.service import get_tenant, tenant_reply_mode

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
    if existing.status in ("processed", "ignored", "monitored", "extracted", "needs_human", "awaiting_reply"):
        return f"already {existing.status}"
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


def _release_thread_claim(db: Session, row: ProcessedThread, success: bool, status: str = "processed") -> None:
    if success:
        row.status = status
        row.processed_at = datetime.utcnow()
    else:
        row.status = "failed"
    db.commit()


def _upsert_processed(
    db: Session,
    tenant_id: str,
    thread_id: str,
    message_id: str,
    status: str,
) -> None:
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
        existing.status = status
        existing.processed_at = datetime.utcnow()
    else:
        db.add(
            ProcessedThread(
                tenant_id=tenant_id,
                gmail_thread_id=thread_id,
                last_message_id=message_id,
                status=status,
            )
        )


def _mark_ignored(
    db: Session,
    tenant_id: str,
    thread_id: str,
    message_id: str,
    subject: str,
    reason: str,
    inbound_body: str = "",
) -> None:
    _upsert_processed(db, tenant_id, thread_id, message_id, "ignored")
    db.add(
        MessageLog(
            tenant_id=tenant_id,
            gmail_thread_id=thread_id,
            direction="ignored",
            subject=subject,
            inbound_body=inbound_body[:8000] if inbound_body else None,
            reply_body=reason,
        )
    )
    db.commit()


def _mark_needs_human(
    db: Session,
    tenant_id: str,
    thread_id: str,
    message_id: str,
    subject: str,
    reason: str,
    inbound_body: str = "",
) -> None:
    _upsert_processed(db, tenant_id, thread_id, message_id, "needs_human")
    db.add(
        MessageLog(
            tenant_id=tenant_id,
            gmail_thread_id=thread_id,
            direction="needs_human",
            subject=subject,
            inbound_body=inbound_body[:8000] if inbound_body else None,
            reply_body=reason,
        )
    )
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

    tenant_row = get_tenant(db, tenant_id)
    ai_on = True if not tenant_row or tenant_row.ai_enabled is None else bool(tenant_row.ai_enabled)

    # AI off: do not touch Gmail (no read, no draft). Caller should also skip polling.
    if not ai_on and not force:
        return {"status": "ai_off", "thread_id": thread_id}

    email_type, classify_reason = await classify_email(
        conversation,
        prompt_template=tenant_row.classify_prompt if tenant_row else None,
    )

    # ignore — leave unread so nothing silently disappears
    if email_type == "ignore" and not force:
        _mark_ignored(
            db, tenant_id, thread_id, latest.message_id, latest.subject, classify_reason, latest.body
        )
        apply_agent_label(gmail, thread_id, LABEL_IGNORED, mark_read=False)
        return {
            "status": "ignored",
            "thread_id": thread_id,
            "reason": classify_reason,
            "marked_read": False,
        }

    # unclear — escalate, leave unread, never draft
    if email_type == "unclear" and not force:
        _mark_needs_human(
            db,
            tenant_id,
            thread_id,
            latest.message_id,
            latest.subject,
            f"Unclear — needs human. {classify_reason}",
            latest.body,
        )
        apply_agent_label(gmail, thread_id, LABEL_NEEDS_HUMAN, mark_read=False)
        return {
            "status": "needs_human",
            "thread_id": thread_id,
            "reason": classify_reason,
            "marked_read": False,
        }

    claim = _claim_thread(db, tenant_id, thread_id, latest.message_id)

    try:
        job = await extract_job_from_thread(
            conversation,
            system_prompt=tenant_row.extraction_system_prompt if tenant_row else None,
            user_prompt_template=tenant_row.extraction_user_prompt if tenant_row else None,
        )
        job = enrich_job_for_pricing(job, conversation)
        if email_type == "booked" and not job.booking_source:
            data = job.model_dump()
            data["booking_source"] = "Moving Helper"
            job = ExtractedJob.model_validate(data)

        # BOOKED: extract only — never draft a sales reply
        if email_type == "booked":
            append_extracted_job(
                db,
                tenant_id,
                job,
                gmail_thread_id=thread_id,
                email_type="booked",
            )
            log = MessageLog(
                tenant_id=tenant_id,
                gmail_thread_id=thread_id,
                direction="extracted",
                subject=latest.subject,
                inbound_body=latest.body[:8000] if latest.body else None,
                extraction_json=json.dumps(job.model_dump()),
                reply_body=f"Booked job — extract only. {classify_reason}",
                rule_name="booked_extract",
            )
            db.add(log)
            _release_thread_claim(db, claim, success=True, status="extracted")
            apply_agent_label(gmail, thread_id, LABEL_EXTRACTED, mark_read=False)
            return {
                "status": "extracted",
                "thread_id": thread_id,
                "email_type": "booked",
                "extraction": job.model_dump(),
                "marked_read": False,
            }

        # INQUIRY: price + stock/YAML reply draft
        try:
            pricing_rows = fetch_pricing_rows(db, tenant_id)
        except Exception as exc:
            logger.exception("Sheet pricing fetch failed for %s: %s", tenant_id, exc)
            pricing_rows = []
        stock_rows = fetch_stock_responses(db, tenant_id)
        quote = compute_quote(job, pricing_rows)
        if not quote:
            logger.warning(
                "QUOTE PENDING for thread %s: %s | extraction movers=%s truck=%s date=%s",
                thread_id,
                quote_failure_reason(job, pricing_rows),
                job.num_movers,
                job.truck_type,
                job.move_date,
            )
        rule_name, reply_body = generate_reply(
            job,
            quote,
            rules_file=tenant_row.rules_file if tenant_row else None,
            reply_template=tenant_row.reply_template if tenant_row else None,
            conversation=conversation,
            stock_rows=stock_rows,
        )

        subject = latest.subject if latest.subject.lower().startswith("re:") else f"Re: {latest.subject}"
        to_email = job.customer_email or latest.from_email

        reply_mode = tenant_reply_mode(tenant_row) if tenant_row else get_settings().reply_mode
        if reply_mode not in ("draft", "send"):
            reply_mode = "draft"

        draft_id = None
        message_id = None
        direction = "draft"

        if reply_mode == "send":
            sent = send_message(gmail, to_email, subject, reply_body, thread_id)
            message_id = sent.get("id")
            direction = "outbound"
        else:
            draft = create_draft(gmail, to_email, subject, reply_body, thread_id)
            draft_id = draft.get("id")
            direction = "draft"

        append_extracted_job(
            db,
            tenant_id,
            job,
            gmail_thread_id=thread_id,
            email_type="inquiry",
        )

        log = MessageLog(
            tenant_id=tenant_id,
            gmail_thread_id=thread_id,
            gmail_message_id=message_id,
            gmail_draft_id=draft_id,
            direction=direction,
            subject=subject,
            inbound_body=latest.body[:8000] if latest.body else None,
            extraction_json=json.dumps(job.model_dump()),
            quote_amount=quote,
            reply_body=reply_body,
            rule_name=rule_name,
        )
        db.add(log)
        # Mark awaiting_reply so follow-up scheduler can resend if no answer
        _release_thread_claim(db, claim, success=True, status="awaiting_reply")

        # Only drafted/sent inquiries get Agent/Drafted + marked read
        apply_agent_label(gmail, thread_id, LABEL_DRAFTED, mark_read=True)

        return {
            "status": "ok",
            "thread_id": thread_id,
            "email_type": "inquiry",
            "extraction": job.model_dump(),
            "quote": quote,
            "rule": rule_name,
            "direction": direction,
            "draft_id": draft_id,
            "message_id": message_id,
            "marked_read": True,
        }
    except Exception:
        _release_thread_claim(db, claim, success=False)
        raise


async def poll_all_tenants(db: Session) -> dict[str, list[dict]]:
    from app.tenants.service import list_pollable_tenants

    out: dict[str, list[dict]] = {}
    for tenant in list_pollable_tenants(db):
        try:
            out[tenant.slug] = await poll_unread_threads(db, tenant.id)
        except Exception as exc:
            logger.exception("Poll failed for tenant %s: %s", tenant.slug, exc)
            out[tenant.slug] = [{"status": "error", "error": str(exc)}]
    return out


async def poll_unread_threads(db: Session, tenant_id: str) -> list[dict]:
    from app.tenants.service import get_tenant, mark_tenant_polled

    tenant = get_tenant(db, tenant_id)
    if tenant is not None and tenant.ai_enabled is False:
        return [{"status": "ai_off", "reason": "AI disabled — inbox not touched"}]

    gmail = get_gmail_service(db, tenant_id)
    thread_ids = list_recent_thread_ids(gmail, query="is:unread in:inbox", max_results=10)
    results = []
    for tid in thread_ids:
        try:
            result = await process_thread(db, tenant_id, tid)
            results.append(result)
        except Exception as exc:
            logger.exception("Failed processing thread %s: %s", tid, exc)
            results.append({"status": "error", "thread_id": tid, "error": str(exc)})
    tenant = get_tenant(db, tenant_id)
    if tenant:
        mark_tenant_polled(db, tenant)
    return results
