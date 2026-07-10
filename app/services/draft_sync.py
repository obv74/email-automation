"""Sync MessageLog draft rows with live Gmail draft/sent state."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import MessageLog
from app.gmail.drafts import get_draft

logger = logging.getLogger(__name__)


def thread_has_sent_reply(gmail, thread_id: Optional[str], reply_body: Optional[str] = None) -> Optional[str]:
    """Return Gmail message id if the thread has an outbound SENT message (manual or API send)."""
    if not thread_id:
        return None
    try:
        thread = (
            gmail.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
    except Exception as exc:
        logger.warning("Could not load thread %s for draft sync: %s", thread_id, exc)
        return None

    for msg in thread.get("messages") or []:
        labels = set(msg.get("labelIds") or [])
        if "SENT" in labels and "DRAFT" not in labels:
            return msg.get("id")
    return None


def sync_draft_log(gmail, log: MessageLog) -> MessageLog:
    """
    Align a draft MessageLog with Gmail:
    - draft still exists → keep as draft
    - draft gone + SENT in thread → mark outbound (Sent)
    - draft gone + no SENT → mark discarded (deleted in Gmail)
    """
    if log.direction != "draft" or not log.gmail_draft_id:
        return log

    draft = get_draft(gmail, log.gmail_draft_id)
    if draft is not None:
        return log

    sent_id = thread_has_sent_reply(gmail, log.gmail_thread_id, log.reply_body)
    if sent_id:
        log.direction = "outbound"
        log.gmail_message_id = sent_id
        log.gmail_draft_id = None
        logger.info("Draft log %s synced as sent (Gmail message %s)", log.id, sent_id)
    else:
        log.direction = "discarded"
        log.gmail_draft_id = None
        logger.info("Draft log %s synced as discarded (draft deleted in Gmail)", log.id)
    return log


def sync_draft_logs(db: Session, gmail, logs: list[MessageLog]) -> list[MessageLog]:
    changed = False
    for log in logs:
        if log.direction != "draft" or not log.gmail_draft_id:
            continue
        before = (log.direction, log.gmail_draft_id, log.gmail_message_id)
        sync_draft_log(gmail, log)
        after = (log.direction, log.gmail_draft_id, log.gmail_message_id)
        if before != after:
            changed = True
    if changed:
        db.commit()
        for log in logs:
            db.refresh(log)
    return logs
