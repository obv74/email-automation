"""Pydantic schema for structured email extraction."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _null_str(v: Any) -> Optional[str]:
    if v in (None, "", "null", "None", "n/a", "N/A"):
        return None
    return str(v).strip() or None


def _yn(v: Any) -> Optional[str]:
    """Normalize yes/no answers to Y, N, or null."""
    if v in (None, "", "null", "None", "n/a", "N/A", "unknown"):
        return None
    s = str(v).strip().lower()
    if s in ("y", "yes", "true", "1"):
        return "Y"
    if s in ("n", "no", "false", "0"):
        return "N"
    if s in ("y", "n"):
        return s.upper()
    return str(v).strip()


class ExtractedJob(BaseModel):
    # Core identity
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    city_state: Optional[str] = None

    # Timing / service
    move_date: Optional[str] = None  # YYYY-MM-DD if stated
    move_time: Optional[str] = None
    service_requested: Optional[str] = None
    load_address: Optional[str] = None
    unload_address: Optional[str] = None

    # Inventory / notes
    inventory: list[str] = Field(default_factory=list)
    heaviest_item: Optional[str] = None
    special_notes: Optional[str] = None
    customer_requests: list[str] = Field(default_factory=list)
    promises_made: list[str] = Field(default_factory=list)

    # Special handling Y/N
    over_250_lbs: Optional[str] = None
    super_fragile: Optional[str] = None
    over_1000_value: Optional[str] = None
    packing: Optional[str] = None
    unpacking: Optional[str] = None
    assembly: Optional[str] = None
    disassembly: Optional[str] = None
    special_handling_notes: Optional[str] = None

    # Pricing block (from thread — not invented)
    minimum_hours: Optional[str] = None
    minimum_price: Optional[str] = None
    hourly_rate: Optional[str] = None
    deposit: Optional[str] = None
    balance_due: Optional[str] = None

    # Crew / truck (for live Sheet quotes on inquiries)
    num_movers: Optional[int] = None
    truck_type: Optional[str] = None  # e.g. "16ft", "26ft"
    booking_source: Optional[str] = None  # e.g. "Moving Helper", "direct"
    summary: str = ""

    @field_validator("summary", mode="before")
    @classmethod
    def summary_not_none(cls, v):
        return v if v is not None else ""

    @field_validator("inventory", "customer_requests", "promises_made", mode="before")
    @classmethod
    def coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v

    @field_validator(
        "customer_name",
        "customer_phone",
        "customer_email",
        "city_state",
        "move_date",
        "move_time",
        "service_requested",
        "load_address",
        "unload_address",
        "heaviest_item",
        "special_notes",
        "special_handling_notes",
        "minimum_hours",
        "minimum_price",
        "hourly_rate",
        "deposit",
        "balance_due",
        "booking_source",
        mode="before",
    )
    @classmethod
    def coerce_optional_str(cls, v):
        return _null_str(v)

    @field_validator(
        "over_250_lbs",
        "super_fragile",
        "over_1000_value",
        "packing",
        "unpacking",
        "assembly",
        "disassembly",
        mode="before",
    )
    @classmethod
    def coerce_yn(cls, v):
        return _yn(v)

    @field_validator("num_movers", mode="before")
    @classmethod
    def coerce_movers(cls, v):
        if v in (None, "", "null"):
            return None
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            return None

    @field_validator("truck_type", mode="before")
    @classmethod
    def coerce_truck(cls, v):
        if v in (None, "", "null", "none", "None"):
            return None
        return str(v).strip()

    def needs_manual_pricing(self) -> bool:
        return self.num_movers is None or not self.move_date

    def title_block(self) -> str:
        """Client's Title Categories format (quick scan line)."""
        parts = [
            f"Client Name: {self.customer_name or ''}",
            f"Phone: {self.customer_phone or ''}",
            f"Date: {self.move_date or ''}",
            f"Time: {self.move_time or ''}",
            f"City, State: {self.city_state or ''}",
            f"Service / Job Description: {self.service_requested or ''}",
            f"Minimum hours: {self.minimum_hours or ''}",
            f"Special Notes: {self.special_notes or ''}",
        ]
        return "\n".join(parts)

    def booking_entry_block(self) -> str:
        """Client's Booking Entry Template."""
        inv = ", ".join(self.inventory) if self.inventory else ""
        reqs = "; ".join(self.customer_requests) if self.customer_requests else ""
        promises = "; ".join(self.promises_made) if self.promises_made else ""
        parts = [
            f"Client Name: {self.customer_name or ''}",
            f"Phone: {self.customer_phone or ''}",
            f"Date: {self.move_date or ''}",
            f"Time: {self.move_time or ''}",
            f"Service / Job Description: {self.service_requested or ''}",
            f"City, State: {self.city_state or ''}",
            f"Load Address: {self.load_address or ''}",
            f"Unload Address: {self.unload_address or ''}",
            f"Inventory List: {inv}",
            f"Heaviest Item: {self.heaviest_item or ''}",
            f"Special Notes: {self.special_notes or ''}",
            f"Customer Requests: {reqs}",
            f"Company Promises: {promises}",
            "",
            "Special Handling:",
            f"Any item over 250 pounds?: {self.over_250_lbs or ''}",
            f"Any super fragile items?: {self.super_fragile or ''}",
            f"Any item over $1000 in value?: {self.over_1000_value or ''}",
            f"Packing?: {self.packing or ''}",
            f"Unpacking?: {self.unpacking or ''}",
            f"Assembly?: {self.assembly or ''}",
            f"Disassembly?: {self.disassembly or ''}",
            f"Special Handling Notes: {self.special_handling_notes or ''}",
            "",
            "Pricing:",
            f"Minimum Hours: {self.minimum_hours or ''}",
            f"Minimum Price: {self.minimum_price or ''}",
            f"Hourly Rate (after minimum): {self.hourly_rate or ''}",
            f"Deposit: {self.deposit or ''}",
            f"Balance Due: {self.balance_due or ''}",
            f"Email: {self.customer_email or ''}",
            f"Truck: {self.truck_type or ''}",
            f"Movers: {self.num_movers or ''}",
            f"Booking source: {self.booking_source or ''}",
        ]
        return "\n".join(parts)

    def copyable_full(self) -> str:
        return (
            "=== TITLE ===\n"
            f"{self.title_block()}\n\n"
            "=== BOOKING ENTRY ===\n"
            f"{self.booking_entry_block()}\n\n"
            "=== SUMMARY ===\n"
            f"{self.summary or ''}"
        )
