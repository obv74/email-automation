"""Read full Gmail threads and parse MIME bodies."""

import base64
import logging
import re
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore


@dataclass
class ParsedMessage:
    message_id: str
    thread_id: str
    subject: str
    from_email: str
    from_name: str
    to_email: str
    date: str
    body: str


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return raw.decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    if BeautifulSoup is None:
        return re.sub(r"<[^>]+>", " ", html)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def _extract_parts(payload: dict) -> tuple[Optional[str], Optional[str]]:
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if body_data:
        text = _decode_body(body_data)
        if mime == "text/plain":
            return text, None
        if mime == "text/html":
            return None, text

    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in payload.get("parts", []) or []:
        p, h = _extract_parts(part)
        if p:
            plain_parts.append(p)
        if h:
            html_parts.append(h)

    plain = "\n".join(plain_parts) if plain_parts else None
    html = "\n".join(html_parts) if html_parts else None
    return plain, html


def _message_body(payload: dict) -> str:
    plain, html = _extract_parts(payload)
    if plain and plain.strip():
        return plain.strip()
    if html:
        return _html_to_text(html)
    return ""


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def parse_message(msg: dict) -> ParsedMessage:
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    from_raw = _header(headers, "From")
    from_name, from_email = parseaddr(from_raw)
    _, to_email = parseaddr(_header(headers, "To"))

    return ParsedMessage(
        message_id=msg["id"],
        thread_id=msg["threadId"],
        subject=_header(headers, "Subject"),
        from_email=from_email,
        from_name=from_name or from_email,
        to_email=to_email,
        date=_header(headers, "Date"),
        body=_message_body(payload),
    )


def format_conversation(messages: list[ParsedMessage]) -> str:
    lines: list[str] = []
    for m in messages:
        lines.append(f"From: {m.from_name} <{m.from_email}>")
        lines.append(f"Date: {m.date}")
        lines.append(f"Subject: {m.subject}")
        lines.append(m.body)
        lines.append("---")
    return "\n".join(lines)


def fetch_full_thread(gmail, thread_id: str) -> tuple[list[ParsedMessage], str]:
    thread = gmail.users().threads().get(userId="me", id=thread_id, format="full").execute()
    raw_messages = thread.get("messages", [])
    parsed = [parse_message(m) for m in raw_messages]
    conversation = format_conversation(parsed)
    return parsed, conversation


def list_recent_thread_ids(gmail, query: str = "is:unread in:inbox", max_results: int = 20) -> list[str]:
    response = (
        gmail.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return [t["id"] for t in response.get("threads", [])]


def mark_thread_as_read(gmail, thread_id: str) -> None:
    """Remove UNREAD so the next poll does not pick the same thread again."""
    gmail.users().threads().modify(
        userId="me",
        id=thread_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
