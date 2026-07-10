"""Fill missing pricing fields when the LLM puts them only in the summary."""

import re
from typing import Optional

from app.extraction.schema import ExtractedJob

_MOVERS_RE = re.compile(
    r"\b(\d+)\s*(?:movers?|men|people|crew)\b",
    re.IGNORECASE,
)
_TRUCK_RE = re.compile(
    r"\b(\d+)\s*(?:ft|foot|feet|'|’)?\s*(?:truck|van)?\b",
    re.IGNORECASE,
)
_TRUCK_SIZE_RE = re.compile(
    r"\b(16|20|22|24|26)\s*(?:ft|foot|feet)\b",
    re.IGNORECASE,
)


def normalize_truck_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip().lower().replace(" ", "")
    text = text.replace("foot", "ft").replace("feet", "ft")
    m = re.search(r"(\d+)\s*ft", text) or re.search(r"(\d+)ft", text)
    if m:
        return f"{m.group(1)}ft"
    # bare number like "16" when context is truck
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


def enrich_job_for_pricing(job: ExtractedJob, conversation: str = "") -> ExtractedJob:
    """Backfill num_movers / truck_type from summary or raw email when LLM omitted them."""
    blob = " ".join(
        part
        for part in (job.summary or "", conversation or "", " ".join(job.customer_requests or []))
        if part
    )

    data = job.model_dump()
    if data.get("num_movers") is None:
        inferred = _infer_movers(blob)
        if inferred is not None:
            data["num_movers"] = inferred

    truck = normalize_truck_type(data.get("truck_type"))
    if not truck:
        truck = _infer_truck(blob)
    data["truck_type"] = truck

    return ExtractedJob.model_validate(data)
