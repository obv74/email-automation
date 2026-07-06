"""Prompt templates for LLM extraction."""

EXTRACTION_SYSTEM = """You extract structured moving-job information from customer email threads.
Return ONLY valid JSON matching the schema exactly. Every field must be present.
Use null for unknown scalar fields and [] for empty lists.
Do not invent prices. Only extract what is explicitly stated or clearly implied.
Distinguish customer_requests (what the customer wants) from promises_made (what the moving company promised).
For truck_type use values like "16ft", "26ft", "small", "large", or null if not mentioned."""

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


def build_extraction_prompt(conversation: str) -> str:
    return f"""Extract job details from this email thread.

Schema:
{EXTRACTION_SCHEMA_HINT}

Email thread (oldest to newest):
---
{conversation}
---

Return JSON only."""


def build_retry_prompt(conversation: str, error: str) -> str:
    return f"""Your previous response was invalid: {error}
Return ONLY valid JSON matching this schema:
{EXTRACTION_SCHEMA_HINT}

Email thread:
---
{conversation}
---"""
