"""FastAPI application entrypoint."""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.google_oauth import disconnect_gmail, exchange_code, get_authorization_url
from app.config import get_settings
from app.dashboard.routes import router as dashboard_router
from app.db.models import ProcessedThread, Tenant, get_db, init_db
from app.gmail.client import get_gmail_service
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids
from app.scheduler.runner import start_scheduler
from app.services.pipeline import poll_unread_threads, process_thread
from app.tenants.service import create_tenant, get_tenant, list_tenants, resolve_tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_oauth_states: dict[str, str] = {}


def _resolve_tenant_or_404(db: Session, tenant_key: str) -> Tenant:
    try:
        return resolve_tenant(db, tenant_key)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()

    db = next(get_db())
    try:
        tenant = db.query(Tenant).filter(Tenant.id == settings.default_tenant_id).first()
        if not tenant:
            tid = settings.default_tenant_id
            tenant = Tenant(
                id=tid,
                slug=tid,
                name=settings.default_tenant_name,
                pricing_sheet_id=settings.pricing_sheet_id or None,
                reply_mode=settings.reply_mode,
                is_active=True,
            )
            db.add(tenant)
            db.commit()
    finally:
        db.close()

    start_scheduler()
    yield


app = FastAPI(title="Email Agent", version="0.1.0", lifespan=lifespan)
app.include_router(dashboard_router)


class CreateTenantBody(BaseModel):
    name: str
    slug: str | None = None
    pricing_sheet_id: str | None = None
    contact_email: str | None = None


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    ollama_ok = False
    ollama_detail = "not checked"
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5.0)
        ollama_ok = r.status_code == 200
        ollama_detail = "running" if ollama_ok else f"status {r.status_code}"
    except Exception as exc:
        ollama_detail = str(exc)

    companies = list_tenants(db, active_only=False)
    connected = sum(1 for t in companies if t.gmail_connected)

    return {
        "status": "ok",
        "companies": len(companies),
        "gmail_connected": connected,
        "ollama_model": settings.ollama_model,
        "ollama": ollama_detail,
        "default_reply_mode": settings.reply_mode,
    }


@app.get("/api/tenants")
def api_list_tenants(db: Session = Depends(get_db)):
    tenants = list_tenants(db, active_only=False)
    return [
        {
            "id": t.id,
            "slug": t.slug,
            "name": t.name,
            "gmail_connected": t.gmail_connected,
            "connected_gmail_email": t.connected_gmail_email,
            "pricing_sheet_id": t.pricing_sheet_id,
            "is_active": t.is_active,
        }
        for t in tenants
    ]


@app.post("/api/tenants")
def api_create_tenant(body: CreateTenantBody, db: Session = Depends(get_db)):
    try:
        tenant = create_tenant(
            db,
            name=body.name,
            slug=body.slug,
            pricing_sheet_id=body.pricing_sheet_id,
            contact_email=body.contact_email,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "dashboard_url": f"/dashboard/{tenant.slug}",
    }


@app.get("/auth/google/disconnect")
def google_disconnect(tenant: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings()
    if tenant:
        t = _resolve_tenant_or_404(db, tenant)
        tenant_id = t.id
        redirect = f"/dashboard/{t.slug}"
    else:
        tenant_id = settings.default_tenant_id
        redirect = "/dashboard"
    disconnect_gmail(db, tenant_id)
    return RedirectResponse(redirect)


@app.get("/auth/google/connect")
def google_connect(tenant: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(400, "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    if tenant:
        t = _resolve_tenant_or_404(db, tenant)
        tenant_id = t.id
    else:
        tenant_id = settings.default_tenant_id
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = tenant_id
    return RedirectResponse(get_authorization_url(state))


@app.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    state = request.query_params.get("state", "")
    if not state:
        raise HTTPException(400, "OAuth failed: missing state parameter")
    tenant_id = _oauth_states.pop(state, settings.default_tenant_id)
    authorization_response = str(request.url)
    try:
        exchange_code(db, tenant_id, state, authorization_response)
    except Exception as exc:
        logger.exception("OAuth callback failed")
        raise HTTPException(400, f"OAuth failed: {exc}") from exc
    tenant = get_tenant(db, tenant_id)
    slug = tenant.slug if tenant else settings.default_tenant_id
    return RedirectResponse(f"/dashboard/{slug}")


@app.get("/api/{tenant_slug}/threads/unread")
def api_list_unread(tenant_slug: str, db: Session = Depends(get_db)):
    tenant = _resolve_tenant_or_404(db, tenant_slug)
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
                    "snippet": (latest.body[:200] + "...") if latest and len(latest.body) > 200 else (latest.body if latest else ""),
                }
            )
        return {"tenant": tenant.slug, "count": len(thread_ids), "thread_ids": thread_ids, "previews": previews}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/{tenant_slug}/threads/{thread_id}/preview")
def api_preview_thread(tenant_slug: str, thread_id: str, db: Session = Depends(get_db)):
    tenant = _resolve_tenant_or_404(db, tenant_slug)
    try:
        gmail = get_gmail_service(db, tenant.id)
        messages, conversation = fetch_full_thread(gmail, thread_id)
        return {
            "tenant": tenant.slug,
            "thread_id": thread_id,
            "message_count": len(messages),
            "messages": [
                {
                    "from": m.from_email,
                    "subject": m.subject,
                    "date": m.date,
                    "body_preview": m.body[:500],
                }
                for m in messages
            ],
            "conversation_length": len(conversation),
        }
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/{tenant_slug}/threads/{thread_id}/process")
async def api_process_thread(
    tenant_slug: str, thread_id: str, force: bool = False, db: Session = Depends(get_db)
):
    tenant = _resolve_tenant_or_404(db, tenant_slug)
    try:
        return await process_thread(db, tenant.id, thread_id, force=force)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/{tenant_slug}/poll")
async def api_poll(tenant_slug: str, db: Session = Depends(get_db)):
    tenant = _resolve_tenant_or_404(db, tenant_slug)
    try:
        return await poll_unread_threads(db, tenant.id)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Poll failed for %s", tenant_slug)
        raise HTTPException(
            500,
            f"Poll failed: {exc}. If Ollama is loading the model, wait 2 min and retry with a long timeout.",
        ) from exc


@app.post("/api/{tenant_slug}/threads/{thread_id}/awaiting-reply")
def mark_awaiting_reply(tenant_slug: str, thread_id: str, db: Session = Depends(get_db)):
    tenant = _resolve_tenant_or_404(db, tenant_slug)
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
