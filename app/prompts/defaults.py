"""Default AI prompts and reply template — used when a company has no custom text."""

CLASSIFY_PROMPT = """Classify this email thread for a MOVING company. Pick ONE type:

- "booked" — job is already booked/paid (Moving Helper, U-Haul Moving Help, payment code, JB- job id, "I booked", confirmation of scheduled crew). Do NOT treat as a new quote request.
- "inquiry" — customer asking about a move, pricing, availability, packing, insurance, or wants to book (not yet booked).
- "ignore" — clearly not moving-related (spam, newsletter, vendor invoice, recruiting).
- "unclear" — might be moving-related but you are not sure. Prefer unclear over ignore.

Return JSON only:
{"email_type": "booked" or "inquiry" or "ignore" or "unclear", "reason": "one short sentence"}

Email thread:
---
{email}
---"""

CLASSIFY_SYSTEM = (
    "You classify moving-company emails. Prefer booked when payment/platform booking "
    "is clear. Prefer unclear over ignore when unsure. Never invent certainty."
)

EXTRACTION_SYSTEM = """Extract moving-job fields as ONE compact JSON object. No markdown.
Keep strings SHORT. inventory max 8 short items. summary max 25 words. promises_made usually [].
Rules:
1) "First Last 1 pm unload…" → customer_name=First Last
2) phone/email from text
3) unload vs load addresses
4) truck like 15ft; U-Haul/Moving Helper → num_movers=2 if unknown
5) "2hrs minimum $159/hr" → minimum_hours=2, hourly_rate=$159/hr
6) Customer U-Haul gear → special_notes, NOT promises_made
Always finish valid JSON (close all braces/quotes)."""

EXTRACTION_USER = """JSON only.
{schema}
{example}
Email:
---
{email}
---
Reply with complete valid JSON now."""

REPLY_TEMPLATE = """Hi {customer_name},

Thank you for contacting us about your move.

Here is what we understood from your email:
{summary}

Load: {load_address}
Unload: {unload_address}
Date: {move_date}
Time: {move_time}

Inventory:
{inventory}

Estimated quote: {quote}

Let us know if you would like to book or if anything needs updating.

Best regards,
Your Moving Team
"""

# Placeholders shown in the Settings UI help text
CLASSIFY_PLACEHOLDERS = "{email}"
EXTRACTION_PLACEHOLDERS = "{email}, {schema}, {example}"
REPLY_PLACEHOLDERS = (
    "{customer_name}, {summary}, {load_address}, {unload_address}, "
    "{move_date}, {move_time}, {inventory}, {customer_requests}, {quote}, "
    "{service_requested}, {customer_phone}, {customer_email}"
)
