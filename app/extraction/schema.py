"""Pydantic schema for structured email extraction."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ExtractedJob(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    load_address: Optional[str] = None
    unload_address: Optional[str] = None
    service_requested: Optional[str] = None
    move_date: Optional[str] = None  # YYYY-MM-DD if stated
    move_time: Optional[str] = None
    inventory: list[str] = Field(default_factory=list)
    customer_requests: list[str] = Field(default_factory=list)
    promises_made: list[str] = Field(default_factory=list)
    num_movers: Optional[int] = None
    truck_type: Optional[str] = None  # e.g. "16ft", "26ft", "none"
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

    def needs_manual_pricing(self) -> bool:
        return self.num_movers is None or not self.move_date
