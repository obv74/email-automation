"""Read pricing data from Google Sheets."""

import logging
from pathlib import Path
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.auth.google_oauth import load_credentials
from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_sheets_service(db: Session, tenant_id: str):
    settings = get_settings()
    if settings.google_service_account_file:
        path = Path(settings.google_service_account_file)
        creds = service_account.Credentials.from_service_account_file(
            str(path),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    creds = load_credentials(db, tenant_id)
    if not creds:
        raise RuntimeError("No credentials for Google Sheets")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def fetch_pricing_rows(db: Session, tenant_id: str, sheet_id: Optional[str] = None) -> list[dict[str, Any]]:
    settings = get_settings()
    sid = sheet_id or settings.pricing_sheet_id
    if not sid:
        raise RuntimeError("PRICING_SHEET_ID is not configured")

    service = _get_sheets_service(db, tenant_id)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range="Pricing!A:Z")
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return []

    headers = [h.strip().lower().replace(" ", "_") for h in values[0]]
    rows: list[dict[str, Any]] = []
    for row in values[1:]:
        item = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        rows.append(item)
    return rows
