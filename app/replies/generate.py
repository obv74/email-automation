"""Generate reply bodies from extraction, quote, and rules."""

from typing import Any, Optional

from app.extraction.schema import ExtractedJob
from app.prompts.defaults import REPLY_TEMPLATE
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
) -> tuple[str, str]:
    custom = (reply_template or "").strip()
    if custom:
        return "custom", render_template(custom, job, quote)

    rules = load_rules(rules_file)
    template_name = pick_template_name(job.summary or "", rules)
    templates: dict[str, Any] = rules.get("templates", {})
    template_body = templates.get(template_name, templates.get("default", ""))
    if not template_body:
        template_body = REPLY_TEMPLATE
    return template_name, render_template(template_body, job, quote)
