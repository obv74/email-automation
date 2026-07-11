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

EXTRACTION_SYSTEM = """You extract structured moving-job information from email threads.
Return ONLY valid JSON matching the schema exactly. Every field must be present.
Use null for unknown scalar fields and [] for empty lists.
Do not invent prices, addresses, or Y/N answers — only extract what is explicitly stated or clearly implied.
Distinguish customer_requests (what the customer wants) from promises_made (what the moving company promised).
For truck_type use values like "15ft", "20ft", "26ft", or null if not mentioned.
For Y/N fields use "Y", "N", or null.
Set booking_source to "Moving Helper", "U-Haul", "direct", or null when clear.
city_state should be like "Alexandria, VA" when known.
special_notes = stairs, elevators, long walks, load-only/unload-only, pads, payment codes, etc.
summary = 2–4 sentences covering the job for ops staff."""

EXTRACTION_USER = """Extract moving job fields as JSON only. All keys required. Use null/[] if missing.

{schema}

Email:
---
{email}
---"""

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
EXTRACTION_PLACEHOLDERS = "{email}, {schema}"
REPLY_PLACEHOLDERS = (
    "{customer_name}, {summary}, {load_address}, {unload_address}, "
    "{move_date}, {move_time}, {inventory}, {customer_requests}, {quote}, "
    "{service_requested}, {customer_phone}, {customer_email}"
)
