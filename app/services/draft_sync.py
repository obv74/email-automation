"""Sync MessageLog rows with live Gmail draft/thread state."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import MessageLog

logger = logging.getLogger(__name__)


def list_live_draft_ids(gmail) -> set[str]:
    """All draft IDs currently in the Gmail Drafts folder."""
    ids: set[str] = set()
    page_token = None
    while True:
        kwargs = {"userId": "me", "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = gmail.users().drafts().list(**kwargs).execute()
        for draft in resp.get("drafts") or []:
            if draft.get("id"):
                ids.add(draft["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def thread_exists(gmail, thread_id: str, cache: dict[str, bool]) -> bool:
    if thread_id in cache:
        return cache[thread_id]
    try:
        gmail.users().threads().get(
            userId="me",
            id=thread_id,
            format="metadata",
            metadataHeaders=["Subject"],
        ).execute()
        cache[thread_id] = True
    except Exception:
        cache[thread_id] = False
    return cache[thread_id]


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
        return None

    for msg in thread.get("messages") or []:
        labels = set(msg.get("labelIds") or [])
        if "SENT" in labels and "DRAFT" not in labels:
            return msg.get("id")
    return None


def purge_logs_for_missing_threads(db: Session, gmail, logs: list[MessageLog]) -> int:
    """
    Delete message-log rows whose Gmail thread no longer exists
    (deleted from Inbox and Trash).
    """
    cache: dict[str, bool] = {}
    deleted = 0
    for log in list(logs):
        thread_id = log.gmail_thread_id
        if not thread_id:
            continue
        if thread_exists(gmail, thread_id, cache):
            continue
        logger.info(
            "Removing log %s (%s) — Gmail thread %s gone (deleted from mailbox)",
            log.id,
            log.subject,
            thread_id,
        )
        db.delete(log)
        deleted += 1
    if deleted:
        db.commit()
    return deleted


def sync_draft_logs(db: Session, gmail, logs: list[MessageLog]) -> dict[str, int]:
    """
    Align draft MessageLogs with Gmail:
    - draft id still in Gmail Drafts → keep (dedupe: one row per draft id)
    - draft gone + SENT in thread → mark Sent
    - draft gone otherwise → delete from dashboard
    """
    counts = {"kept": 0, "sent": 0, "deleted": 0, "live_gmail_drafts": 0}
    try:
        live_ids = list_live_draft_ids(gmail)
    except Exception as exc:
        logger.warning("Could not list Gmail drafts: %s", exc)
        return counts

    counts["live_gmail_drafts"] = len(live_ids)
    logger.info("Gmail has %s live draft(s); checking %s dashboard draft row(s)", len(live_ids), len(logs))

    ordered = sorted(logs, key=lambda r: r.created_at or r.id, reverse=True)
    seen_draft_ids: set[str] = set()
    seen_threads: set[str] = set()

    for log in ordered:
        if log.direction != "draft":
            continue

        draft_id = log.gmail_draft_id
        thread_id = log.gmail_thread_id

        if draft_id and draft_id in seen_draft_ids:
            logger.info("Removing duplicate draft log %s (draft %s)", log.id, draft_id)
            db.delete(log)
            counts["deleted"] += 1
            continue
        if thread_id and thread_id in seen_threads:
            logger.info("Removing duplicate draft log %s (thread %s)", log.id, thread_id)
            db.delete(log)
            counts["deleted"] += 1
            continue

        if not draft_id:
            logger.info("Draft log %s has no gmail_draft_id — deleting", log.id)
            db.delete(log)
            counts["deleted"] += 1
            continue

        if draft_id in live_ids:
            seen_draft_ids.add(draft_id)
            if thread_id:
                seen_threads.add(thread_id)
            counts["kept"] += 1
            continue

        sent_id = thread_has_sent_reply(gmail, thread_id)
        if sent_id:
            log.direction = "outbound"
            log.gmail_message_id = sent_id
            log.gmail_draft_id = None
            if thread_id:
                seen_threads.add(thread_id)
            logger.info("Draft log %s → Sent (message %s)", log.id, sent_id)
            counts["sent"] += 1
        else:
            logger.info("Draft log %s deleted (not in Gmail Drafts)", log.id)
            db.delete(log)
            counts["deleted"] += 1

    if counts["sent"] or counts["deleted"]:
        db.commit()
    logger.info("Draft sync done: %s", counts)
    return counts
