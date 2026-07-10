"""Default AI prompts and reply template — used when a company has no custom text."""

CLASSIFY_PROMPT = """Does this email thread look like a customer inquiry for a MOVING company?
Examples YES: quote request, move date, load/unload addresses, movers, packing, inventory for a move.
Examples NO: marketing newsletter, vendor invoice, personal chat, recruiting spam, unrelated business.

Return JSON only:
{"is_moving_inquiry": true or false, "reason": "one short sentence"}

Email thread:
---
{email}
---"""

CLASSIFY_SYSTEM = "You classify whether emails are moving-company customer inquiries."

EXTRACTION_SYSTEM = """You extract structured moving-job information from customer email threads.
Return ONLY valid JSON matching the schema exactly. Every field must be present.
Use null for unknown scalar fields and [] for empty lists.
Do not invent prices. Only extract what is explicitly stated or clearly implied.
Distinguish customer_requests (what the customer wants) from promises_made (what the moving company promised).
For truck_type use values like "16ft", "26ft", "small", "large", or null if not mentioned."""

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
