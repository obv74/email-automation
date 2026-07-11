"""Email type classification: booked / inquiry / ignore / unclear."""

from __future__ import annotations

import re
from typing import Literal, Optional

EmailType = Literal["booked", "inquiry", "ignore", "unclear"]

# Strong signals that this is an already-booked 3rd-party job (leave alone for replies).
_BOOKED_PATTERNS = [
    re.compile(r"moving\s*helper", re.I),
    re.compile(r"movinghelp", re.I),
    re.compile(r"u-?haul'?s?\s+moving\s+help", re.I),
    re.compile(r"payment\s+code", re.I),
    re.compile(r"\bJB-[a-z0-9]+\b", re.I),
    re.compile(r"load/unload\s*-\s*JB-", re.I),
    re.compile(r"\bi\s+booked\b", re.I),
    re.compile(r"\bbooked\s+a\s+\d+-?person", re.I),
    re.compile(r"through\s+u-?haul", re.I),
    re.compile(r"entering\s+payment\s+code\s+prior\s+to\s+job", re.I),
]


def heuristic_booked(conversation: str) -> bool:
    """Fast keyword check for already-booked Moving Helper / U-Haul style threads."""
    if not conversation:
        return False
    # Sample start + end — platform notices often appear mid/end of thread dumps
    sample = conversation[:6000] + "\n" + conversation[-4000:]
    return any(p.search(sample) for p in _BOOKED_PATTERNS)


def normalize_email_type(raw: Optional[str]) -> EmailType:
    if not raw:
        return "unclear"
    v = str(raw).strip().lower()
    if v in ("booked", "booked_job", "already_booked"):
        return "booked"
    if v in ("inquiry", "lead", "quote", "moving", "yes", "true"):
        return "inquiry"
    if v in ("ignore", "ignored", "not_moving", "no", "false", "spam"):
        return "ignore"
    if v in ("unclear", "uncertain", "needs_human", "maybe"):
        return "unclear"
    return "unclear"
