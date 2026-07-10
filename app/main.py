"""FastAPI application entrypoint."""

import logging
import secrets
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.auth_routes import router as auth_router
from app.api.tenant_routes import router as tenant_api_router
from app.auth.deps import get_user_from_token_param, require_tenant_access
from app.auth.google_oauth import disconnect_gmail, exchange_code, get_authorization_url
from app.config import get_settings
from app.dashboard.routes import router as dashboard_router
from app.db.models import Tenant, get_db, init_db
from app.scheduler.runner import start_scheduler
from app.tenants.service import get_tenant, resolve_tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OAuthState(TypedDict):
    tenant_id: str


_oauth_states: dict[str, OAuthState] = {}


def _frontend_settings_url(query: str = "") -> str:
    settings = get_settings()
    base = settings.frontend_url.rstrip("/")
    path = "/settings"
    if query:
        return f"{base}{path}?{query}"
    return f"{base}{path}"


def _frontend_dashboard_url(query: str = "") -> str:
    settings = get_settings()
    base = settings.frontend_url.rstrip("/")
    path = "/dashboard"
    if query:
        return f"{base}{path}?{query}"
    return f"{base}{path}"


def _resolve_tenant_or_404(db: Session, tenant_key: str) -> Tenant:
    try:
        return resolve_tenant(db, tenant_key)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


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


app = FastAPI(title="Email Agent API", version="0.2.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tenant_api_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    settings = get_settings()
    if settings.frontend_url:
        return RedirectResponse(settings.frontend_url.rstrip("/"))
    return RedirectResponse("/dashboard")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    ollama_detail = "not checked"
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5.0)
        ollama_detail = "running" if r.status_code == 200 else f"status {r.status_code}"
    except Exception as exc:
        ollama_detail = str(exc)

    from app.tenants.service import list_tenants

    companies = list_tenants(db, active_only=False)
    connected = sum(1 for t in companies if t.gmail_connected)

    return {
        "status": "ok",
        "companies": len(companies),
        "gmail_connected": connected,
        "ollama_model": settings.ollama_model,
        "ollama": ollama_detail,
        "frontend_url": settings.frontend_url,
    }


@app.get("/auth/google/connect")
def google_connect(
    tenant: str,
    token: str,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(400, "Google OAuth is not configured.")

    user = get_user_from_token_param(token, db)
    t = _resolve_tenant_or_404(db, tenant)
    require_tenant_access(db, user, t.slug)

    state = secrets.token_urlsafe(16)
    _oauth_states[state] = {"tenant_id": t.id}
    return RedirectResponse(get_authorization_url(state))


@app.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    state = request.query_params.get("state", "")
    if not state:
        raise HTTPException(400, "OAuth failed: missing state parameter")

    oauth_state = _oauth_states.pop(state, None)
    tenant_id = oauth_state["tenant_id"] if oauth_state else settings.default_tenant_id
    authorization_response = str(request.url)
    try:
        exchange_code(db, tenant_id, state, authorization_response)
    except Exception as exc:
        logger.exception("OAuth callback failed")
        raise HTTPException(400, f"OAuth failed: {exc}") from exc

    tenant = get_tenant(db, tenant_id)
    slug = tenant.slug if tenant else settings.default_tenant_id
    if settings.frontend_url:
        return RedirectResponse(_frontend_settings_url("gmail=connected"))
    return RedirectResponse("/dashboard")


@app.get("/auth/google/disconnect")
def google_disconnect_legacy(tenant: str, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token_param(token, db)
    t = _resolve_tenant_or_404(db, tenant)
    require_tenant_access(db, user, t.slug)
    disconnect_gmail(db, t.id)
    if get_settings().frontend_url:
        return RedirectResponse(_frontend_settings_url("gmail=disconnected"))
    return RedirectResponse("/dashboard")
