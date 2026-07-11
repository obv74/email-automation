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
Use ONLY facts from the email. If missing → null or []. Never invent floors, phones, prices, or names.
Keep strings SHORT. inventory max 8 items. summary max 25 words. promises_made usually [].
Rules:
1) Name only if stated (e.g. "Best, Joshua" → "Joshua").
2) phone/email only if in the email.
3) Unload-only job → unload_address set, load_address=null. Load-only → opposite.
4) special_notes = ONLY access notes from THIS email (floor #, elevator, walk distance). Never invent.
5) truck like 15ft if mentioned. U-Haul/Moving Helper with unknown crew → num_movers=2.
6) minimum_hours/hourly_rate only if stated in email, else null.
7) Customer-owned U-Haul gear → special_notes, not promises_made.
8) Preferred time window like "1-3pm" or "as early as 12pm" → move_time.
Always close all braces/quotes (valid JSON)."""

EXTRACTION_USER = """JSON only from THIS email. null if not stated.
{schema}
Email:
---
{email}
---
Complete valid JSON now."""

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
