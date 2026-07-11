"""Prompt templates for LLM extraction — tuned for small/slow Ollama (accuracy + speed)."""

from typing import Optional

from app.prompts.defaults import EXTRACTION_SYSTEM, EXTRACTION_USER

# Slim schema = fewer output tokens = much faster on CPU. Enrich fills Y/N etc.
EXTRACTION_SCHEMA_HINT = """{
  "customer_name": string|null,
  "customer_phone": string|null,
  "customer_email": string|null,
  "city_state": string|null,
  "load_address": string|null,
  "unload_address": string|null,
  "service_requested": string|null,
  "move_date": "YYYY-MM-DD"|null,
  "move_time": string|null,
  "inventory": [string],
  "heaviest_item": string|null,
  "special_notes": string|null,
  "customer_requests": [string],
  "promises_made": [string],
  "minimum_hours": string|null,
  "hourly_rate": string|null,
  "num_movers": int|null,
  "truck_type": string|null,
  "booking_source": string|null,
  "summary": string
}"""

# Different job than typical unload tests — reduces copy-from-example errors.
FEW_SHOT_EXAMPLE = """
FORMAT EXAMPLE (do NOT copy these values — they are fake):
{"customer_name":"Alex Kim","customer_phone":"(202) 555-0100","customer_email":"alex@example.com","city_state":"Arlington, VA","load_address":"100 Main St Arlington VA","unload_address":null,"service_requested":"load only","move_date":null,"move_time":"10 am","inventory":["desk","chair","boxes"],"heaviest_item":"desk","special_notes":"2nd floor no elevator","customer_requests":["load only"],"promises_made":[],"minimum_hours":"3","hourly_rate":"$120/hr","num_movers":2,"truck_type":"20ft","booking_source":"direct","summary":"Load-only for Alex in Arlington 2nd floor."}
"""


def build_extraction_prompt(conversation: str, user_template: Optional[str] = None) -> str:
    template = (user_template or EXTRACTION_USER).strip() or EXTRACTION_USER
    if "{email}" in template:
        body = (
            template.replace("{schema}", EXTRACTION_SCHEMA_HINT)
            .replace("{example}", FEW_SHOT_EXAMPLE)
            .replace("{email}", conversation)
        )
    else:
        body = f"{template}\n\nEmail:\n---\n{conversation}\n---"
        if "{schema}" in body:
            body = body.replace("{schema}", EXTRACTION_SCHEMA_HINT)
        if "{example}" in body:
            body = body.replace("{example}", FEW_SHOT_EXAMPLE)
    return body


def build_retry_prompt(conversation: str, error: str) -> str:
    # Keep retry tiny — speed matters on CPU. No few-shot on retry (avoids leakage).
    return f"""Fix JSON only. Error: {error}
Use ONLY facts from the email. null if missing. Never invent phone/price/name.
Schema: {EXTRACTION_SCHEMA_HINT}
Email:
---
{conversation[:3500]}
---"""


__all__ = [
    "EXTRACTION_SCHEMA_HINT",
    "EXTRACTION_SYSTEM",
    "FEW_SHOT_EXAMPLE",
    "build_extraction_prompt",
    "build_retry_prompt",
]
