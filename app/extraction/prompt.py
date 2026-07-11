"""Prompt templates for LLM extraction — tuned for small/slow Ollama (accuracy + speed)."""

from typing import Optional

from app.prompts.defaults import EXTRACTION_SYSTEM, EXTRACTION_USER

# Slim schema = fewer output tokens. Enrich fills Y/N etc.
# No few-shot: small models copy example facts into real jobs.
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


def build_extraction_prompt(conversation: str, user_template: Optional[str] = None) -> str:
    template = (user_template or EXTRACTION_USER).strip() or EXTRACTION_USER
    if "{email}" in template:
        body = template.replace("{schema}", EXTRACTION_SCHEMA_HINT).replace("{email}", conversation)
        # Drop leftover {example} if an old custom prompt still has it
        body = body.replace("{example}", "")
    else:
        body = f"{template}\n\nEmail:\n---\n{conversation}\n---"
        if "{schema}" in body:
            body = body.replace("{schema}", EXTRACTION_SCHEMA_HINT)
        body = body.replace("{example}", "")
    return body


def build_retry_prompt(conversation: str, error: str) -> str:
    return f"""Fix JSON only. Error: {error}
Use ONLY facts from the email. null if missing. Never invent phone/price/name/floor.
Schema: {EXTRACTION_SCHEMA_HINT}
Email:
---
{conversation[:3500]}
---"""


__all__ = [
    "EXTRACTION_SCHEMA_HINT",
    "EXTRACTION_SYSTEM",
    "build_extraction_prompt",
    "build_retry_prompt",
]
