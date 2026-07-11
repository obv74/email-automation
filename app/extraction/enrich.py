"""Fill missing fields when the LLM omits obvious details from the text."""

from __future__ import annotations

import re
from typing import Optional

from app.extraction.schema import ExtractedJob

_MOVERS_RE = re.compile(
    r"\b(\d+)\s*(?:movers?|men|people|crew|person)\b",
    re.IGNORECASE,
)
_TRUCK_RE = re.compile(
    r"\b(\d+)\s*(?:ft|foot|feet|'|’)?\s*(?:truck|van)?\b",
    re.IGNORECASE,
)
_TRUCK_SIZE_RE = re.compile(
    r"\b(15|16|17|20|22|24|26)\s*(?:ft|foot|feet|'|’)\b",
    re.IGNORECASE,
)
# "Joshua Soberano 1 pm unload 15ft truck North Bethesda, MD (404) 450-7688 |"
_LEAD_NAME_RE = re.compile(
    r"^\s*([A-Z][a-zA-Z'''\-]+(?:\s+[A-Z][a-zA-Z'''\-]+){0,3})\s+"
    r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|morning|afternoon|evening)",
    re.MULTILINE,
)
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_HOURS_RE = re.compile(
    r"(?:pd\s+)?(\d+)\s*(?:hrs?|hours?)\s*minimum|minimum\s+(\d+)\s*(?:hrs?|hours?)",
    re.IGNORECASE,
)
_RATE_RE = re.compile(r"\$?\s*(\d{2,4})\s*/\s*hr", re.IGNORECASE)
_NO_HEAVY_RE = re.compile(
    r"no\s+(?:oversized|oversize|extremely\s+heavy|heavy\s+items)|"
    r"nothing\s+over\s+\d+\s*lbs?|no\s+single\s+item\s+over",
    re.IGNORECASE,
)
_UNLOAD_ONLY_RE = re.compile(
    r"\bunload(?:ing)?\s+only\b|\bjust\s+be\s+unloading\b|\bunloading\s+at\b|"
    r"\bunload\s+\d+\s*ft|\bunload\s+\d+ft|\bmoving\s+in\b",
    re.IGNORECASE,
)
_LOAD_ONLY_RE = re.compile(r"\bload(?:ing)?\s+only\b|\bneed\s+help\s+with\s+loading\b", re.IGNORECASE)
_UHAUL_RE = re.compile(r"u-?haul|moving\s*helper", re.IGNORECASE)


def normalize_truck_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip().lower().replace(" ", "")
    text = text.replace("foot", "ft").replace("feet", "ft").replace("'", "").replace("’", "")
    m = re.search(r"(\d+)\s*ft", text) or re.search(r"(\d+)ft", text) or re.search(r"(\d+)truck", text)
    if m:
        return f"{m.group(1)}ft"
    if text.isdigit():
        return f"{text}ft"
    return text or None


def _infer_movers(text: str) -> Optional[int]:
    m = _MOVERS_RE.search(text)
    if not m:
        return None
    try:
        n = int(m.group(1))
        return n if 1 <= n <= 20 else None
    except ValueError:
        return None


def _infer_truck(text: str) -> Optional[str]:
    m = _TRUCK_SIZE_RE.search(text) or _TRUCK_RE.search(text)
    if not m:
        return None
    return normalize_truck_type(f"{m.group(1)}ft")


def _infer_name(text: str) -> Optional[str]:
    m = _LEAD_NAME_RE.search(text or "")
    if not m:
        return None
    name = m.group(1).strip()
    # Avoid capturing service words
    if name.lower() in {"the", "truck", "unload", "load", "uhaul", "moving"}:
        return None
    return name


_ASSEMBLY_YES_RE = re.compile(
    r"\b(?:need|needs|want|require)s?\s+(?:help\s+with\s+)?(?:assembly|assemble|breakdown|disassemble)",
    re.IGNORECASE,
)
_ASSEMBLY_NO_RE = re.compile(
    r"okay\s+with\s+assembly\s+just\s+need\s+manpower|no\s+assembly|assembly\s+not\s+needed",
    re.IGNORECASE,
)
_PACK_YES_RE = re.compile(r"\b(?:need|want|require)s?\s+(?:full\s+)?packing\b|\bpack(?:ing)?\s+(?:service|help)\b", re.I)
_UNPACK_YES_RE = re.compile(r"\b(?:need|want|require)s?\s+unpacking\b|\bunpack(?:ing)?\s+(?:service|help)\b", re.I)


def enrich_job_for_pricing(job: ExtractedJob, conversation: str = "") -> ExtractedJob:
    """Backfill obvious fields the LLM missed from the raw email text."""
    blob = " ".join(
        part
        for part in (
            job.summary or "",
            conversation or "",
            " ".join(job.customer_requests or []),
            job.service_requested or "",
            job.special_notes or "",
        )
        if part
    )
    raw = conversation or ""

    data = job.model_dump()

    if not data.get("customer_name"):
        inferred = _infer_name(raw) or _infer_name(blob)
        if inferred:
            data["customer_name"] = inferred

    if not data.get("customer_phone"):
        m = _PHONE_RE.search(raw) or _PHONE_RE.search(blob)
        if m:
            data["customer_phone"] = m.group(0)

    if not data.get("customer_email"):
        m = _EMAIL_RE.search(raw) or _EMAIL_RE.search(blob)
        if m:
            data["customer_email"] = m.group(0)

    if data.get("num_movers") is None:
        inferred = _infer_movers(blob)
        if inferred is not None:
            data["num_movers"] = inferred
        elif _UHAUL_RE.search(blob):
            data["num_movers"] = 2

    truck = normalize_truck_type(data.get("truck_type"))
    if not truck:
        truck = _infer_truck(blob)
    data["truck_type"] = truck

    if not data.get("minimum_hours"):
        m = _HOURS_RE.search(blob)
        if m:
            data["minimum_hours"] = m.group(1) or m.group(2)

    if not data.get("hourly_rate"):
        m = _RATE_RE.search(blob)
        if m:
            data["hourly_rate"] = f"${m.group(1)}/hr"

    if not data.get("booking_source") and _UHAUL_RE.search(blob):
        data["booking_source"] = "U-Haul" if re.search(r"u-?haul", blob, re.I) else "Moving Helper"

    unload_only = bool(_UNLOAD_ONLY_RE.search(blob)) or (
        (data.get("service_requested") or "").lower().find("unload") >= 0
        and "load" not in (data.get("service_requested") or "").lower().replace("unload", "")
    )
    load_only = bool(_LOAD_ONLY_RE.search(blob))
    if unload_only or load_only:
        if not _PACK_YES_RE.search(blob):
            data["packing"] = "N"
        if unload_only and not _UNPACK_YES_RE.search(blob):
            data["unpacking"] = "N"
        if load_only and not _UNPACK_YES_RE.search(blob):
            if data.get("unpacking") in (None, ""):
                data["unpacking"] = "N"

    if _PACK_YES_RE.search(blob):
        data["packing"] = "Y"
    if _UNPACK_YES_RE.search(blob):
        data["unpacking"] = "Y"

    if _NO_HEAVY_RE.search(blob):
        data["over_250_lbs"] = "N"
        if not data.get("heaviest_item"):
            data["heaviest_item"] = "none noted"

    if _ASSEMBLY_NO_RE.search(blob):
        data["assembly"] = "N"
    elif _ASSEMBLY_YES_RE.search(blob):
        data["assembly"] = "Y"

    promises = list(data.get("promises_made") or [])
    cleaned = []
    for p in promises:
        pl = str(p).lower()
        if "hand truck" in pl or ("u-haul" in pl and "truck" in pl and "assign" in pl):
            notes = data.get("special_notes") or ""
            extra = str(p).strip()
            if extra and extra.lower() not in notes.lower():
                data["special_notes"] = f"{notes}; {extra}".strip("; ")
            continue
        cleaned.append(p)
    data["promises_made"] = cleaned

    return ExtractedJob.model_validate(data)
