"""Minimal dashboard routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MessageLog, Tenant, get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/dashboard/templates")


@router.get("", response_class=HTMLResponse)
def dashboard_home(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    tenant = db.query(Tenant).filter(Tenant.id == settings.default_tenant_id).first()
    logs = (
        db.query(MessageLog)
        .filter(MessageLog.tenant_id == settings.default_tenant_id)
        .order_by(MessageLog.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenant": tenant,
            "logs": logs,
            "settings": settings,
        },
    )
