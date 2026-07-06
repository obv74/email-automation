"""Create Gmail drafts and send replies."""

import base64
from email.mime.text import MIMEText
from typing import Optional


def _build_raw_message(to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return payload


def create_draft(gmail, to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    payload = _build_raw_message(to, subject, body, thread_id)
    return gmail.users().drafts().create(userId="me", body={"message": payload}).execute()


def send_message(gmail, to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    payload = _build_raw_message(to, subject, body, thread_id)
    return gmail.users().messages().send(userId="me", body=payload).execute()
