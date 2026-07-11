"""Protected tenant and message APIs."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CreateTenantBody, ExtractThreadBody, MessageLogOut, TenantOut, UpdateTenantBody
from app.auth.deps import get_current_user, require_tenant_access
from app.auth.google_oauth import disconnect_gmail
from app.db.models import MessageLog, ProcessedThread, User, get_db
from app.gmail.client import get_gmail_service
from app.gmail.drafts import send_draft, send_message
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids, list_thread_previews
from app.services.draft_sync import purge_logs_for_missing_threads, sync_draft_logs
from app.services.pipeline import extract_chosen_thread, poll_unread_threads, process_thread
from app.tenants.service import (
    create_tenant,
    get_or_create_user_company,
    list_tenants_for_user,
    tenant_to_dict,
    update_tenant_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


def _tenant_out(tenant) -> TenantOut:
    return TenantOut(**tenant_to_dict(tenant))


def _parse_summary(extraction_json: Optional[str]) -> Optional[str]:
    if not extraction_json:
        return None
    try:
        data = json.loads(extraction_json)
        return data.get("summary")
    except (json.JSONDecodeError, TypeError):
        return None


def _log_out(log: MessageLog, draft_exists: Optional[bool] = None) -> MessageLogOut:
    can_send = log.direction == "draft" and bool(log.reply_body or log.gmail_draft_id)
    if draft_exists is False:
        can_send = False
    return MessageLogOut(
        id=log.id,
        direction=log.direction,
        subject=log.subject,
        quote_amount=log.quote_amount,
        rule_name=log.rule_name,
        reply_body=log.reply_body,
        inbound_body=log.inbound_body,
        summary=_parse_summary(log.extraction_json),
        extraction_json=log.extraction_json,
        gmail_thread_id=log.gmail_thread_id,
        gmail_draft_id=log.gmail_draft_id,
        gmail_message_id=log.gmail_message_id,
        draft_exists=draft_exists,
        can_send=can_send,
        created_at=log.created_at,
    )


@router.get("/company", response_model=TenantOut)
def api_get_my_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = get_or_create_user_company(db, user.id, user.name or "", user.email)
    return _tenant_out(tenant)


@router.patch("/company", response_model=TenantOut)
def api_update_my_company(
    body: UpdateTenantBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = get_or_create_user_company(db, user.id, user.name or "", user.email)
    try:
        tenant = update_tenant_settings(
            db,
            tenant,
            name=body.name,
            pricing_sheet_id=body.pricing_sheet_id,
            reply_mode=body.reply_mode,
            poll_interval_minutes=body.poll_interval_minutes,
            ai_enabled=body.ai_enabled,
            classify_prompt=body.classify_prompt,
            extraction_system_prompt=body.extraction_system_prompt,
            extraction_user_prompt=body.extraction_user_prompt,
            reply_template=body.reply_template,
            reset_prompts=body.reset_prompts,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _tenant_out(tenant)


@router.get("/tenants", response_model=list[TenantOut])
def api_list_tenants(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_tenant_out(t) for t in list_tenants_for_user(db, user.id)]


@router.post("/tenants", response_model=TenantOut)
def api_create_tenant(
    body: CreateTenantBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        tenant = create_tenant(
            db,
            name=body.name,
            slug=body.slug,
            pricing_sheet_id=body.pricing_sheet_id,
            contact_email=body.contact_email,
            owner_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _tenant_out(tenant)


@router.get("/tenants/{tenant_slug}", response_model=TenantOut)
def api_get_tenant(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    return _tenant_out(tenant)


@router.patch("/tenants/{tenant_slug}", response_model=TenantOut)
def api_update_tenant(
    tenant_slug: str,
    body: UpdateTenantBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        tenant = update_tenant_settings(
            db,
            tenant,
            name=body.name,
            pricing_sheet_id=body.pricing_sheet_id,
            reply_mode=body.reply_mode,
            poll_interval_minutes=body.poll_interval_minutes,
            ai_enabled=body.ai_enabled,
            classify_prompt=body.classify_prompt,
            extraction_system_prompt=body.extraction_system_prompt,
            extraction_user_prompt=body.extraction_user_prompt,
            reply_template=body.reply_template,
            reset_prompts=body.reset_prompts,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _tenant_out(tenant)


@router.get("/tenants/{tenant_slug}/logs", response_model=list[MessageLogOut])
def api_tenant_logs(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 100,
):
    tenant = require_tenant_access(db, user, tenant_slug)

    if tenant.gmail_connected:
        try:
            gmail = get_gmail_service(db, tenant.id)

            # 1) Sync drafts with Gmail Drafts folder
            draft_candidates = (
                db.query(MessageLog)
                .filter(
                    MessageLog.tenant_id == tenant.id,
                    MessageLog.direction == "draft",
                )
                .all()
            )
            if draft_candidates:
                sync_draft_logs(db, gmail, draft_candidates)

            # 2) Remove any log whose Gmail thread was deleted (Inbox + Trash)
            all_with_thread = (
                db.query(MessageLog)
                .filter(
                    MessageLog.tenant_id == tenant.id,
                    MessageLog.gmail_thread_id.isnot(None),
                )
                .order_by(MessageLog.created_at.desc())
                .limit(min(limit, 500))
                .all()
            )
            removed = purge_logs_for_missing_threads(db, gmail, all_with_thread)
            if removed:
                logger.info("Purged %s logs with deleted Gmail threads for %s", removed, tenant_slug)
        except RuntimeError as exc:
            logger.warning("Gmail log sync skipped for %s: %s", tenant_slug, exc)

    # Drop leftover soft-deleted rows from older versions
    db.query(MessageLog).filter(
        MessageLog.tenant_id == tenant.id,
        MessageLog.direction == "discarded",
    ).delete(synchronize_session=False)
    db.commit()

    logs = (
        db.query(MessageLog)
        .filter(
            MessageLog.tenant_id == tenant.id,
            MessageLog.direction != "discarded",
        )
        .order_by(MessageLog.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [
        _log_out(log, True if log.direction == "draft" and log.gmail_draft_id else None)
        for log in logs
    ]


@router.post("/tenants/{tenant_slug}/logs/{log_id}/send")
def api_send_log_reply(
    tenant_slug: str,
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    log = (
        db.query(MessageLog)
        .filter(MessageLog.tenant_id == tenant.id, MessageLog.id == log_id)
        .first()
    )
    if not log:
        raise HTTPException(404, "Message not found")
    if log.direction == "outbound":
        raise HTTPException(400, "Already sent")

    gmail = get_gmail_service(db, tenant.id)
    message_id = None
    try:
        if log.gmail_draft_id:
            sent = send_draft(gmail, log.gmail_draft_id)
            message_id = sent.get("id")
        elif log.reply_body:
            sent = send_message(
                gmail,
                _reply_to_from_log(log),
                log.subject or "Re: your move",
                log.reply_body,
                log.gmail_thread_id,
            )
            message_id = sent.get("id")
        else:
            raise HTTPException(400, "Nothing to send")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Send failed for log %s", log_id)
        raise HTTPException(500, f"Send failed: {exc}") from exc

    log.direction = "outbound"
    log.gmail_message_id = message_id
    log.gmail_draft_id = None
    db.commit()
    return {"status": "ok", "message_id": message_id}


def _reply_to_from_log(log: MessageLog) -> str:
    if log.extraction_json:
        try:
            data = json.loads(log.extraction_json)
            if data.get("customer_email"):
                return data["customer_email"]
        except (json.JSONDecodeError, TypeError):
            pass
    return "customer@example.com"


@router.post("/tenants/{tenant_slug}/gmail/disconnect")
def api_disconnect_gmail(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    disconnect_gmail(db, tenant.id)
    return {"status": "ok", "slug": tenant.slug, "gmail_connected": False}


@router.get("/tenants/{tenant_slug}/threads/recent")
def api_list_recent(
    tenant_slug: str,
    q: str = "in:inbox newer_than:30d",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent inbox threads with real API ids — for manual Extract picker."""
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        gmail = get_gmail_service(db, tenant.id)
        previews = list_thread_previews(gmail, query=q, max_results=25)
        return {"tenant": tenant.slug, "count": len(previews), "previews": previews}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/tenants/{tenant_slug}/threads/unread")
def api_list_unread(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        gmail = get_gmail_service(db, tenant.id)
        previews = list_thread_previews(gmail, query="is:unread in:inbox", max_results=25)
        return {
            "tenant": tenant.slug,
            "count": len(previews),
            "thread_ids": [p["thread_id"] for p in previews],
            "previews": previews,
        }
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/tenants/{tenant_slug}/extract")
async def api_extract_chosen(
    tenant_slug: str,
    body: ExtractThreadBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract job categories from ONE Gmail thread the user chose. No auto-inbox scan."""
    tenant = require_tenant_access(db, user, tenant_slug)
    if not tenant.gmail_connected:
        raise HTTPException(400, "Connect Gmail first")
    try:
        return await extract_chosen_thread(db, tenant.id, body.thread_ref)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Manual extract failed for %s", tenant_slug)
        raise HTTPException(500, f"Extract failed: {exc}") from exc


@router.post("/tenants/{tenant_slug}/poll")
async def api_poll(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        return await poll_unread_threads(db, tenant.id)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Poll failed for %s", tenant_slug)
        raise HTTPException(500, f"Poll failed: {exc}") from exc


@router.post("/tenants/{tenant_slug}/threads/{thread_id}/process")
async def api_process_thread(
    tenant_slug: str,
    thread_id: str,
    force: bool = False,
    extract_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        return await process_thread(
            db, tenant.id, thread_id, force=force, extract_only=extract_only
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/tenants/{tenant_slug}/threads/{thread_id}/awaiting-reply")
def mark_awaiting_reply(
    tenant_slug: str,
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    row = (
        db.query(ProcessedThread)
        .filter(
            ProcessedThread.tenant_id == tenant.id,
            ProcessedThread.gmail_thread_id == thread_id,
        )
        .first()
    )
    if not row:
        row = ProcessedThread(
            tenant_id=tenant.id,
            gmail_thread_id=thread_id,
            last_message_id="",
            status="awaiting_reply",
        )
        db.add(row)
    else:
        row.status = "awaiting_reply"
    db.commit()
    return {"status": "ok", "tenant": tenant.slug, "thread_id": thread_id}
