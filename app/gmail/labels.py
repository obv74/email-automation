"""Gmail label helpers: Agent/Drafted, Needs-Human, Ignored, Extracted."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

LABEL_DRAFTED = "Agent/Drafted"
LABEL_NEEDS_HUMAN = "Agent/Needs-Human"
LABEL_IGNORED = "Agent/Ignored"
LABEL_EXTRACTED = "Agent/Extracted"

AGENT_LABELS = (LABEL_DRAFTED, LABEL_NEEDS_HUMAN, LABEL_IGNORED, LABEL_EXTRACTED)


def _list_label_map(gmail) -> dict[str, str]:
    """name -> id"""
    result = gmail.users().labels().list(userId="me").execute()
    return {lb["name"]: lb["id"] for lb in result.get("labels", [])}


def ensure_label(gmail, name: str) -> str:
    """Return label id, creating the label if missing."""
    labels = _list_label_map(gmail)
    if name in labels:
        return labels[name]
    created = (
        gmail.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    logger.info("Created Gmail label %s", name)
    return created["id"]


def ensure_agent_labels(gmail) -> dict[str, str]:
    return {name: ensure_label(gmail, name) for name in AGENT_LABELS}


def apply_agent_label(
    gmail,
    thread_id: str,
    label_name: str,
    *,
    mark_read: bool = False,
) -> None:
    """
    Apply one Agent/* label to the thread.
    Removes other Agent/* labels so the thread has a single agent status.
    Only removes UNREAD when mark_read=True (Drafted path).
    """
    try:
        label_ids = ensure_agent_labels(gmail)
        add_id = label_ids[label_name]
        remove_ids = [label_ids[n] for n in AGENT_LABELS if n != label_name]
        if mark_read:
            remove_ids.append("UNREAD")

        gmail.users().threads().modify(
            userId="me",
            id=thread_id,
            body={
                "addLabelIds": [add_id],
                "removeLabelIds": remove_ids,
            },
        ).execute()
    except Exception as exc:
        logger.warning("Failed to apply label %s on thread %s: %s", label_name, thread_id, exc)


def label_for_status(status: str) -> Optional[str]:
    mapping = {
        "draft": LABEL_DRAFTED,
        "outbound": LABEL_DRAFTED,
        "ignored": LABEL_IGNORED,
        "needs_human": LABEL_NEEDS_HUMAN,
        "extracted": LABEL_EXTRACTED,
    }
    return mapping.get(status)
