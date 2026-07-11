"""Google Sheets: pricing, stock replies, extracted job writeback."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.auth.google_oauth import load_credentials
from app.config import get_settings
from app.extraction.schema import ExtractedJob
from app.tenants.service import get_tenant, tenant_pricing_sheet_id

logger = logging.getLogger(__name__)

SHEETS_SCOPES_READONLY = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEETS_SCOPES_RW = ["https://www.googleapis.com/auth/spreadsheets"]

STOCK_TAB_CANDIDATES = ("StockResponses", "Stock Responses", "Stock", "stock_responses")
EXTRACTED_TAB = "ExtractedJobs"

EXTRACTED_HEADERS = [
    "extracted_at",
    "gmail_thread_id",
    "email_type",
    "customer_name",
    "customer_phone",
    "customer_email",
    "city_state",
    "move_date",
    "move_time",
    "service_requested",
    "load_address",
    "unload_address",
    "inventory",
    "heaviest_item",
    "special_notes",
    "customer_requests",
    "promises_made",
    "over_250_lbs",
    "super_fragile",
    "over_1000_value",
    "packing",
    "unpacking",
    "assembly",
    "disassembly",
    "special_handling_notes",
    "minimum_hours",
    "minimum_price",
    "hourly_rate",
    "deposit",
    "balance_due",
    "num_movers",
    "truck_type",
    "booking_source",
    "summary",
    "title_block",
    "booking_entry_block",
]


def _get_sheets_service(db: Session, tenant_id: str, *, write: bool = False):
    settings = get_settings()
    scopes = SHEETS_SCOPES_RW if write else SHEETS_SCOPES_READONLY
    if settings.google_service_account_file:
        path = Path(settings.google_service_account_file)
        creds = service_account.Credentials.from_service_account_file(str(path), scopes=scopes)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    creds = load_credentials(db, tenant_id)
    if not creds:
        raise RuntimeError("No credentials for Google Sheets")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _sheet_id_for_tenant(db: Session, tenant_id: str, sheet_id: Optional[str] = None) -> str:
    tenant = get_tenant(db, tenant_id)
    sid = sheet_id or (tenant_pricing_sheet_id(tenant) if tenant else None) or get_settings().pricing_sheet_id
    if not sid:
        raise RuntimeError("PRICING_SHEET_ID is not configured for this company")
    return sid


def _rows_to_dicts(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values:
        return []
    headers = [str(h).strip().lower().replace(" ", "_") for h in values[0]]
    rows: list[dict[str, Any]] = []
    for row in values[1:]:
        item = {
            headers[i]: (row[i].strip() if isinstance(row[i], str) else row[i]) if i < len(row) else ""
            for i in range(len(headers))
            if headers[i]
        }
        rows.append(item)
    return rows


def fetch_pricing_rows(db: Session, tenant_id: str, sheet_id: Optional[str] = None) -> list[dict[str, Any]]:
    sid = _sheet_id_for_tenant(db, tenant_id, sheet_id)
    service = _get_sheets_service(db, tenant_id, write=False)
    result = service.spreadsheets().values().get(spreadsheetId=sid, range="Pricing!A:Z").execute()
    rows = _rows_to_dicts(result.get("values", []))
    logger.info("Loaded %s pricing rows for tenant %s from sheet %s", len(rows), tenant_id, sid)
    return rows


def _find_stock_tab(service, spreadsheet_id: str) -> Optional[str]:
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title").execute()
    except HttpError:
        return None
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    for candidate in STOCK_TAB_CANDIDATES:
        if candidate in titles:
            return candidate
    # case-insensitive fallback
    lower = {t.lower(): t for t in titles}
    for candidate in STOCK_TAB_CANDIDATES:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def fetch_stock_responses(db: Session, tenant_id: str, sheet_id: Optional[str] = None) -> list[dict[str, str]]:
    """
    Load stock replies from a StockResponses (or similar) tab.

    Expected columns (flexible names):
      - trigger / if_contains / keyword
      - body / response / reply / template
      - name (optional)
    """
    try:
        sid = _sheet_id_for_tenant(db, tenant_id, sheet_id)
    except RuntimeError:
        return []

    try:
        service = _get_sheets_service(db, tenant_id, write=False)
        tab = _find_stock_tab(service, sid)
        if not tab:
            return []
        result = service.spreadsheets().values().get(spreadsheetId=sid, range=f"'{tab}'!A:Z").execute()
        rows = _rows_to_dicts(result.get("values", []))
    except Exception as exc:
        logger.info("Stock responses sheet unavailable for %s: %s", tenant_id, exc)
        return []

    out: list[dict[str, str]] = []
    for row in rows:
        trigger = (
            row.get("trigger")
            or row.get("if_contains")
            or row.get("keyword")
            or row.get("trigger_word")
            or ""
        )
        body = row.get("body") or row.get("response") or row.get("reply") or row.get("template") or ""
        name = row.get("name") or row.get("template_name") or trigger[:40]
        if trigger and body:
            out.append({"trigger": str(trigger).strip(), "body": str(body), "name": str(name).strip() or "stock"})
    logger.info("Loaded %s stock responses for tenant %s", len(out), tenant_id)
    return out


def match_stock_response(
    stock_rows: list[dict[str, str]],
    haystack: str,
) -> Optional[dict[str, str]]:
    """First trigger that appears in haystack (case-insensitive). Longer triggers first."""
    if not stock_rows or not haystack:
        return None
    text = haystack.lower()
    ordered = sorted(stock_rows, key=lambda r: len(r["trigger"]), reverse=True)
    for row in ordered:
        if row["trigger"].lower() in text:
            return row
    return None


def _ensure_extracted_tab(service, spreadsheet_id: str) -> None:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title").execute()
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if EXTRACTED_TAB not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": EXTRACTED_TAB}}}]},
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{EXTRACTED_TAB}'!A1",
            valueInputOption="RAW",
            body={"values": [EXTRACTED_HEADERS]},
        ).execute()
        logger.info("Created %s tab on sheet %s", EXTRACTED_TAB, spreadsheet_id)
        return

    # Ensure header row exists
    existing = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{EXTRACTED_TAB}'!A1:Z1")
        .execute()
        .get("values", [])
    )
    if not existing:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{EXTRACTED_TAB}'!A1",
            valueInputOption="RAW",
            body={"values": [EXTRACTED_HEADERS]},
        ).execute()


def append_extracted_job(
    db: Session,
    tenant_id: str,
    job: ExtractedJob,
    *,
    gmail_thread_id: str = "",
    email_type: str = "",
    sheet_id: Optional[str] = None,
) -> bool:
    """Append one extracted job row to ExtractedJobs tab. Returns False if skipped/failed."""
    try:
        sid = _sheet_id_for_tenant(db, tenant_id, sheet_id)
    except RuntimeError:
        logger.info("No sheet configured — skip ExtractedJobs write for %s", tenant_id)
        return False

    try:
        service = _get_sheets_service(db, tenant_id, write=True)
        _ensure_extracted_tab(service, sid)

        def j(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, list):
                return "; ".join(str(x) for x in v)
            return str(v)

        row = [
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            gmail_thread_id,
            email_type,
            j(job.customer_name),
            j(job.customer_phone),
            j(job.customer_email),
            j(job.city_state),
            j(job.move_date),
            j(job.move_time),
            j(job.service_requested),
            j(job.load_address),
            j(job.unload_address),
            j(job.inventory),
            j(job.heaviest_item),
            j(job.special_notes),
            j(job.customer_requests),
            j(job.promises_made),
            j(job.over_250_lbs),
            j(job.super_fragile),
            j(job.over_1000_value),
            j(job.packing),
            j(job.unpacking),
            j(job.assembly),
            j(job.disassembly),
            j(job.special_handling_notes),
            j(job.minimum_hours),
            j(job.minimum_price),
            j(job.hourly_rate),
            j(job.deposit),
            j(job.balance_due),
            j(job.num_movers),
            j(job.truck_type),
            j(job.booking_source),
            j(job.summary),
            job.title_block(),
            job.booking_entry_block(),
        ]
        service.spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"'{EXTRACTED_TAB}'!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        logger.info("Appended ExtractedJobs row for tenant %s thread %s", tenant_id, gmail_thread_id)
        return True
    except Exception as exc:
        logger.warning("ExtractedJobs write failed for %s: %s", tenant_id, exc)
        return False
