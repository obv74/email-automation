"""Prompt templates for LLM extraction."""

from typing import Optional

from app.prompts.defaults import EXTRACTION_SYSTEM, EXTRACTION_USER

EXTRACTION_SCHEMA_HINT = """{
  "customer_name": string or null,
  "customer_phone": string or null,
  "customer_email": string or null,
  "load_address": string or null,
  "unload_address": string or null,
  "service_requested": string or null,
  "move_date": "YYYY-MM-DD" or null,
  "move_time": string or null,
  "inventory": [string],
  "customer_requests": [string],
  "promises_made": [string],
  "num_movers": integer or null,
  "truck_type": string or null,
  "summary": string
}"""


def build_extraction_prompt(conversation: str, user_template: Optional[str] = None) -> str:
    template = (user_template or EXTRACTION_USER).strip() or EXTRACTION_USER
    if "{email}" in template:
        body = template.replace("{schema}", EXTRACTION_SCHEMA_HINT).replace("{email}", conversation)
    else:
        # Custom prompt without placeholder — append email so extraction still works
        body = f"{template}\n\nEmail:\n---\n{conversation}\n---"
        if "{schema}" in body:
            body = body.replace("{schema}", EXTRACTION_SCHEMA_HINT)
    return body


def build_retry_prompt(conversation: str, error: str) -> str:
    return f"""Your previous response was invalid: {error}
Return ONLY valid JSON matching this schema:
{EXTRACTION_SCHEMA_HINT}

Email thread:
---
{conversation}
---"""


# Re-export for callers that imported EXTRACTION_SYSTEM from here
__all__ = [
    "EXTRACTION_SCHEMA_HINT",
    "EXTRACTION_SYSTEM",
    "build_extraction_prompt",
    "build_retry_prompt",
]
