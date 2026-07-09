"""Dashboard routes — multi-company."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MessageLog, get_db
from app.tenants.service import create_tenant, list_tenants, resolve_tenant

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/dashboard/templates")


@router.get("", response_class=HTMLResponse)
def dashboard_home(request: Request, db: Session = Depends(get_db)):
    tenants = list_tenants(db, active_only=False)
    return templates.TemplateResponse(
        request,
        "tenants.html",
        {"tenants": tenants, "settings": get_settings()},
    )


@router.post("/companies")
def create_company(
    name: str = Form(...),
    slug: str | None = Form(None),
    pricing_sheet_id: str | None = Form(None),
    contact_email: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        tenant = create_tenant(
            db,
            name=name,
            slug=slug or None,
            pricing_sheet_id=pricing_sheet_id or None,
            contact_email=contact_email or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(f"/dashboard/{tenant.slug}", status_code=303)


@router.get("/{tenant_slug}", response_class=HTMLResponse)
def tenant_dashboard(tenant_slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        tenant = resolve_tenant(db, tenant_slug)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    logs = (
        db.query(MessageLog)
        .filter(MessageLog.tenant_id == tenant.id)
        .order_by(MessageLog.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tenant": tenant, "logs": logs, "settings": get_settings()},
    )
