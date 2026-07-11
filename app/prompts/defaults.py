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

EXTRACTION_SYSTEM = """Extract moving-job fields as compact JSON. No markdown. No extra keys.
Rules:
1) Name: line like "First Last 1 pm unload…" → customer_name = First Last.
2) Phone (###) ###-#### → customer_phone. email → customer_email.
3) unload/load only: set load_address or unload_address correctly; other null.
4) Inventory as short item list. special_notes = stairs/floor/elevator/walk/pads.
5) promises_made = only what THIS company promised. Customer U-Haul gear → special_notes, not promises.
6) truck_type like 15ft. U-Haul/Moving Helper with no crew size → num_movers=2.
7) "2hrs minimum $159/hr" → minimum_hours=2, hourly_rate=$159/hr.
8) summary = 1-2 short sentences. null if unknown. [] if no list items."""

EXTRACTION_USER = """Return JSON only for this email.
{schema}
{example}
NOW extract this email:
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
EXTRACTION_PLACEHOLDERS = "{email}, {schema}, {example}"
REPLY_PLACEHOLDERS = (
    "{customer_name}, {summary}, {load_address}, {unload_address}, "
    "{move_date}, {move_time}, {inventory}, {customer_requests}, {quote}, "
    "{service_requested}, {customer_phone}, {customer_email}"
)
