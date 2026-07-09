"""FastAPI application entrypoint."""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.google_oauth import disconnect_gmail, exchange_code, get_authorization_url
from app.config import get_settings
from app.dashboard.routes import router as dashboard_router
from app.db.models import ProcessedThread, Tenant, get_db, init_db
from app.scheduler.runner import start_scheduler
from app.gmail.client import get_gmail_service
from app.gmail.threads import fetch_full_thread, list_recent_thread_ids
from app.services.pipeline import poll_unread_threads, process_thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_oauth_states: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()

    db = next(get_db())
    try:
        tenant = db.query(Tenant).filter(Tenant.id == settings.default_tenant_id).first()
        if not tenant:
            tenant = Tenant(
                id=settings.default_tenant_id,
                name=settings.default_tenant_name,
                pricing_sheet_id=settings.pricing_sheet_id or None,
            )
            db.add(tenant)
            db.commit()
    finally:
        db.close()

    start_scheduler(settings.default_tenant_id)
    yield


app = FastAPI(title="Email Agent", version="0.1.0", lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
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

    return {
        "status": "ok",
        "tenant": settings.default_tenant_id,
        "ollama_model": settings.ollama_model,
        "ollama": ollama_detail,
        "reply_mode": settings.reply_mode,
    }


@app.get("/auth/google/disconnect")
def google_disconnect(db: Session = Depends(get_db)):
    """Remove saved Gmail token so you can connect a different account."""
    settings = get_settings()
    disconnect_gmail(db, settings.default_tenant_id)
    return RedirectResponse("/dashboard")


@app.get("/auth/google/connect")
def google_connect():
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(400, "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = settings.default_tenant_id
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
    return RedirectResponse("/dashboard")


@app.get("/api/threads/unread")
def api_list_unread(db: Session = Depends(get_db)):
    """Step 1 test: confirm Gmail API sees unread threads (no Ollama)."""
    settings = get_settings()
    try:
        gmail = get_gmail_service(db, settings.default_tenant_id)
        thread_ids = list_recent_thread_ids(gmail, query="is:unread", max_results=10)
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
        return {"count": len(thread_ids), "thread_ids": thread_ids, "previews": previews}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/threads/{thread_id}/preview")
def api_preview_thread(thread_id: str, db: Session = Depends(get_db)):
    """Step 2 test: read full thread from Gmail (no Ollama)."""
    settings = get_settings()
    try:
        gmail = get_gmail_service(db, settings.default_tenant_id)
        messages, conversation = fetch_full_thread(gmail, thread_id)
        return {
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


@app.post("/api/threads/{thread_id}/process")
async def api_process_thread(thread_id: str, force: bool = False, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        return await process_thread(db, settings.default_tenant_id, thread_id, force=force)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/poll")
async def api_poll(db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        return await poll_unread_threads(db, settings.default_tenant_id)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Poll failed")
        raise HTTPException(
            500,
            f"Poll failed: {exc}. If Ollama is loading the model, wait 2 min and retry with a long timeout.",
        ) from exc


@app.post("/api/threads/{thread_id}/awaiting-reply")
def mark_awaiting_reply(thread_id: str, db: Session = Depends(get_db)):
    """Mark a thread for no-response follow-up (after you send initial outreach)."""
    settings = get_settings()
    row = (
        db.query(ProcessedThread)
        .filter(
            ProcessedThread.tenant_id == settings.default_tenant_id,
            ProcessedThread.gmail_thread_id == thread_id,
        )
        .first()
    )
    if not row:
        row = ProcessedThread(
            tenant_id=settings.default_tenant_id,
            gmail_thread_id=thread_id,
            last_message_id="",
            status="awaiting_reply",
        )
        db.add(row)
    else:
        row.status = "awaiting_reply"
    db.commit()
    return {"status": "ok", "thread_id": thread_id}
