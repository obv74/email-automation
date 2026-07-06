"""Compute quote from extracted job fields and sheet pricing rows."""

from datetime import datetime
from typing import Any, Optional

from app.extraction.schema import ExtractedJob


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


def compute_quote(job: ExtractedJob, pricing_rows: list[dict[str, Any]]) -> Optional[str]:
    if job.needs_manual_pricing():
        return None

    day = _day_of_week(job.move_date)  # type: ignore[arg-type]
    movers = job.num_movers
    truck = (job.truck_type or "").lower()

    best: Optional[float] = None
    for row in pricing_rows:
        row_day = str(row.get("day_of_week", row.get("day", ""))).lower()
        if row_day and row_day != day:
            continue

        row_movers = row.get("num_movers", row.get("movers"))
        if row_movers not in ("", None):
            try:
                if int(row_movers) != movers:
                    continue
            except (TypeError, ValueError):
                continue

        row_truck = str(row.get("truck_type", row.get("truck", ""))).lower()
        if row_truck and truck and row_truck != truck:
            continue

        amount = _parse_amount(row.get("price", row.get("rate", row.get("amount"))))
        if amount is not None:
            best = amount

    if best is None:
        return None
    return f"${best:,.2f}"
