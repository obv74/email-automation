"""Generate reply bodies from extraction, quote, sheet stock, and YAML rules."""

from typing import Any, Optional

from app.extraction.schema import ExtractedJob
from app.prompts.defaults import REPLY_TEMPLATE
from app.pricing.sheets import match_stock_response
from app.replies.rules import load_rules, pick_template_name


def _format_list(items: list[str]) -> str:
    if not items:
        return "Not specified"
    return "\n".join(f"- {item}" for item in items)


def render_template(template: str, job: ExtractedJob, quote: Optional[str]) -> str:
    inventory = _format_list(job.inventory)
    requests = _format_list(job.customer_requests)
    quote_text = quote or "[QUOTE PENDING — please confirm movers, date, and truck size]"

    replacements = {
        "{customer_name}": job.customer_name or "there",
        "{customer_phone}": job.customer_phone or "",
        "{customer_email}": job.customer_email or "",
        "{load_address}": job.load_address or "TBD",
        "{unload_address}": job.unload_address or "TBD",
        "{service_requested}": job.service_requested or "moving service",
        "{move_date}": job.move_date or "TBD",
        "{move_time}": job.move_time or "TBD",
        "{inventory}": inventory,
        "{customer_requests}": requests,
        "{quote}": quote_text,
        "{summary}": job.summary or "",
        "{heaviest_item}": job.heaviest_item or "",
        "{special_notes}": job.special_notes or "",
        "{city_state}": job.city_state or "",
        "{truck_type}": job.truck_type or "",
        "{minimum_hours}": job.minimum_hours or "",
        "{hourly_rate}": job.hourly_rate or "",
    }
    body = template
    for key, value in replacements.items():
        body = body.replace(key, value)
    return body


def generate_reply(
    job: ExtractedJob,
    quote: Optional[str],
    rules_file: Optional[str] = None,
    reply_template: Optional[str] = None,
    *,
    conversation: str = "",
    stock_rows: Optional[list[dict[str, str]]] = None,
) -> tuple[str, str]:
    """
    Priority:
      1. Sheet stock response if a trigger matches the email/summary
      2. Per-tenant custom reply_template (Settings)
      3. YAML keyword rules
      4. Default template
    """
    haystack = "\n".join(
        part
        for part in (
            conversation or "",
            job.summary or "",
            " ".join(job.customer_requests or []),
            job.service_requested or "",
        )
        if part
    )
    matched = match_stock_response(stock_rows or [], haystack)
    if matched:
        return f"stock:{matched['name']}", render_template(matched["body"], job, quote)

    custom = (reply_template or "").strip()
    if custom:
        return "custom", render_template(custom, job, quote)

    rules = load_rules(rules_file)
    template_name = pick_template_name(haystack or job.summary or "", rules)
    templates: dict[str, Any] = rules.get("templates", {})
    template_body = templates.get(template_name, templates.get("default", ""))
    if not template_body:
        template_body = REPLY_TEMPLATE
    return template_name, render_template(template_body, job, quote)


def render_confirmation(
    job_name: Optional[str],
    move_date: Optional[str],
    load_address: Optional[str],
    description: Optional[str],
    days_before: int,
    *,
    rules_file: Optional[str] = None,
) -> tuple[str, str]:
    """Subject + body for booked-job confirmation emails."""
    rules = load_rules(rules_file)
    templates: dict[str, Any] = rules.get("templates", {})
    template = templates.get("confirmation") or (
        "Hi {customer_name},\n\n"
        "This confirms your move on {move_date} ({days_before} day(s) away).\n\n"
        "Load: {load_address}\n"
        "Details: {description}\n\n"
        "Reply if anything changed.\n\n"
        "Thank you!\n"
    )
    fake = ExtractedJob(
        customer_name=job_name,
        move_date=move_date,
        load_address=load_address,
        summary=description or "",
        service_requested=description,
    )
    body = render_template(template, fake, None)
    body = body.replace("{days_before}", str(days_before))
    body = body.replace("{description}", description or "N/A")
    when = "day-before" if days_before == 1 else f"{days_before}-day"
    subject = f"Move confirmation — {when} — {move_date or 'upcoming'}"
    return subject, body
