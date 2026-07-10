"""Compute quote from extracted job fields and sheet pricing rows."""

import logging
import re
from datetime import datetime
from typing import Any, Optional

from app.extraction.enrich import normalize_truck_type
from app.extraction.schema import ExtractedJob

logger = logging.getLogger(__name__)


def _day_of_week(move_date: str) -> str:
    dt = datetime.strptime(move_date, "%Y-%m-%d")
    return dt.strftime("%A").lower()


def _parse_amount(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    text = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_movers(value: Any) -> Optional[int]:
    if value in ("", None):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        m = re.search(r"\d+", str(value))
        return int(m.group(0)) if m else None


def quote_failure_reason(job: ExtractedJob, pricing_rows: list[dict[str, Any]]) -> str:
    if not job.move_date:
        return "missing move_date"
    if job.num_movers is None:
        return "missing num_movers"
    if not pricing_rows:
        return "no pricing rows from sheet (check Sheet ID, tab name Pricing, and share access)"
    try:
        day = _day_of_week(job.move_date)
    except ValueError:
        return f"invalid move_date {job.move_date!r}"
    truck = normalize_truck_type(job.truck_type) or ""
    return (
        f"no sheet row for day={day} movers={job.num_movers} truck={truck or '(any)'} "
        f"({len(pricing_rows)} rows loaded)"
    )


def compute_quote(job: ExtractedJob, pricing_rows: list[dict[str, Any]]) -> Optional[str]:
    if job.needs_manual_pricing():
        logger.info("Quote skipped: %s", quote_failure_reason(job, pricing_rows))
        return None

    day = _day_of_week(job.move_date)  # type: ignore[arg-type]
    movers = job.num_movers
    truck = normalize_truck_type(job.truck_type) or ""

    best: Optional[float] = None
    for row in pricing_rows:
        row_day = str(row.get("day_of_week", row.get("day", ""))).strip().lower()
        if row_day and row_day != day:
            continue

        row_movers = _parse_movers(row.get("num_movers", row.get("movers")))
        if row_movers is not None and row_movers != movers:
            continue

        row_truck = normalize_truck_type(
            str(row.get("truck_type", row.get("truck", "")) or "")
        ) or ""
        if row_truck and truck and row_truck != truck:
            continue

        amount = _parse_amount(row.get("price", row.get("rate", row.get("amount"))))
        if amount is not None:
            best = amount

    if best is None:
        logger.info("Quote skipped: %s", quote_failure_reason(job, pricing_rows))
        return None
    return f"${best:,.2f}"
