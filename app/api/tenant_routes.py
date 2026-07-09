"""Protected tenant and message APIs."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CreateTenantBody, MessageLogOut, TenantOut
from app.auth.deps import get_current_user, require_tenant_access
from app.auth.google_oauth import disconnect_gmail
from app.db.models import MessageLog, ProcessedThread, User, get_db
from app.gmail.client import get_gmail_service
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids
from app.services.pipeline import poll_unread_threads, process_thread
from app.tenants.service import create_tenant, list_tenants_for_user, tenant_to_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


def _tenant_out(tenant) -> TenantOut:
    d = tenant_to_dict(tenant)
    return TenantOut(**d)


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


@router.get("/tenants/{tenant_slug}/logs", response_model=list[MessageLogOut])
def api_tenant_logs(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 100,
):
    tenant = require_tenant_access(db, user, tenant_slug)
    logs = (
        db.query(MessageLog)
        .filter(MessageLog.tenant_id == tenant.id)
        .order_by(MessageLog.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [
        MessageLogOut(
            id=log.id,
            direction=log.direction,
            subject=log.subject,
            quote_amount=log.quote_amount,
            rule_name=log.rule_name,
            reply_body=log.reply_body,
            gmail_thread_id=log.gmail_thread_id,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.post("/tenants/{tenant_slug}/gmail/disconnect")
def api_disconnect_gmail(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    disconnect_gmail(db, tenant.id)
    return {"status": "ok", "slug": tenant.slug, "gmail_connected": False}


@router.get("/tenants/{tenant_slug}/threads/unread")
def api_list_unread(
    tenant_slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        gmail = get_gmail_service(db, tenant.id)
        thread_ids = list_recent_thread_ids(gmail, query="is:unread in:inbox", max_results=10)
        previews = []
        for tid in thread_ids[:5]:
            messages, _ = fetch_full_thread(gmail, tid)
            latest = messages[-1] if messages else None
            previews.append(
                {
                    "thread_id": tid,
                    "subject": latest.subject if latest else "",
                    "from": latest.from_email if latest else "",
                    "snippet": (latest.body[:200] + "...")
                    if latest and len(latest.body) > 200
                    else (latest.body if latest else ""),
                }
            )
        return {"tenant": tenant.slug, "count": len(thread_ids), "thread_ids": thread_ids, "previews": previews}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = require_tenant_access(db, user, tenant_slug)
    try:
        return await process_thread(db, tenant.id, thread_id, force=force)
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
