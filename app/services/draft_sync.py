"""Sync MessageLog draft rows with live Gmail draft/sent state."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import MessageLog
from app.gmail.drafts import get_draft

logger = logging.getLogger(__name__)


def thread_has_sent_reply(gmail, thread_id: Optional[str]) -> Optional[str]:
    """Return Gmail message id if the thread has an outbound SENT message."""
    if not thread_id:
        return None
    try:
        thread = (
            gmail.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
    except Exception:
        # Thread deleted/trashed — not sent
        return None

    for msg in thread.get("messages") or []:
        labels = set(msg.get("labelIds") or [])
        if "SENT" in labels and "DRAFT" not in labels:
            return msg.get("id")
    return None


def sync_draft_log(db: Session, gmail, log: MessageLog) -> str:
    """
    Align a draft MessageLog with Gmail.
    Returns: kept | sent | deleted
    """
    if log.direction != "draft":
        return "kept"

    # No draft id — cannot verify; remove from dashboard
    if not log.gmail_draft_id:
        logger.info("Draft log %s has no gmail_draft_id — deleting from dashboard", log.id)
        db.delete(log)
        return "deleted"

    draft = get_draft(gmail, log.gmail_draft_id)
    if draft is not None:
        return "kept"

    sent_id = thread_has_sent_reply(gmail, log.gmail_thread_id)
    if sent_id:
        log.direction = "outbound"
        log.gmail_message_id = sent_id
        log.gmail_draft_id = None
        logger.info("Draft log %s synced as sent (Gmail message %s)", log.id, sent_id)
        return "sent"

    # Draft deleted in Gmail (and thread missing or no SENT) — remove from dashboard
    logger.info("Draft log %s deleted from dashboard (Gmail draft gone)", log.id)
    db.delete(log)
    return "deleted"


def sync_draft_logs(db: Session, gmail, logs: list[MessageLog]) -> dict[str, int]:
    counts = {"kept": 0, "sent": 0, "deleted": 0}
    for log in list(logs):
        result = sync_draft_log(db, gmail, log)
        counts[result] = counts.get(result, 0) + 1
    if counts["sent"] or counts["deleted"]:
        db.commit()
    logger.info("Draft sync done: %s", counts)
    return counts
