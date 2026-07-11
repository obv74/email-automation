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

# One compact few-shot — big accuracy win on 3B models, still cheap.
FEW_SHOT_EXAMPLE = """
EXAMPLE
Input:
Joshua Soberano 1 pm unload 15ft truck North Bethesda, MD (404) 450-7688 | 9th floor, loading dock by elevator, 150-200ft walk.
Unload: 5411 McGrath Blvd, North Bethesda, MD 20852. Inventory: couch, loveseat, bedframe, mattresses, table, rugs. No oversized/heavy. Uhaul pd 2hrs minimum $159/hr. joshua.soberano@outlook.com

Output:
{"customer_name":"Joshua Soberano","customer_phone":"(404) 450-7688","customer_email":"joshua.soberano@outlook.com","city_state":"North Bethesda, MD","load_address":null,"unload_address":"5411 McGrath Blvd, North Bethesda, MD 20852","service_requested":"unload","move_date":null,"move_time":"1 pm","inventory":["couch","loveseat","bedframe","mattresses","table","rugs"],"heaviest_item":"none noted","special_notes":"9th floor; loading dock by elevator; 150-200ft walk; customer has U-Haul hand truck","customer_requests":["unload only","manpower to apartment"],"promises_made":[],"minimum_hours":"2","hourly_rate":"$159/hr","num_movers":2,"truck_type":"15ft","booking_source":"U-Haul","summary":"Joshua Soberano unload 15ft U-Haul at Wentworth House, North Bethesda; 9th floor via loading-dock elevator; 2hr min $159/hr."}
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
    # Keep retry tiny — speed matters on CPU
    return f"""Fix JSON only. Error: {error}
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
