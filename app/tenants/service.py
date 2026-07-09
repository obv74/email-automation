"""Multi-tenant helpers — each company is an isolated row in shared tables."""

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Tenant


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:48] or "company"


def get_tenant(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_tenant_by_slug(db: Session, slug: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.slug == slug).first()


def resolve_tenant(db: Session, tenant_key: str) -> Tenant:
    """Look up by slug or internal id."""
    tenant = get_tenant_by_slug(db, tenant_key) or get_tenant(db, tenant_key)
    if not tenant:
        raise ValueError(f"Unknown company: {tenant_key}")
    if not tenant.is_active:
        raise ValueError(f"Company inactive: {tenant_key}")
    return tenant


def list_tenants(db: Session, active_only: bool = True) -> list[Tenant]:
    q = db.query(Tenant).order_by(Tenant.name)
    if active_only:
        q = q.filter(Tenant.is_active.is_(True))
    return q.all()


def list_pollable_tenants(db: Session) -> list[Tenant]:
    return (
        db.query(Tenant)
        .filter(Tenant.is_active.is_(True), Tenant.gmail_connected.is_(True))
        .order_by(Tenant.name)
        .all()
    )


def create_tenant(
    db: Session,
    name: str,
    slug: Optional[str] = None,
    pricing_sheet_id: Optional[str] = None,
    contact_email: Optional[str] = None,
) -> Tenant:
    settings = get_settings()
    final_slug = slugify(slug or name)
    if db.query(Tenant).filter(Tenant.slug == final_slug).first():
        raise ValueError(f"Company slug already exists: {final_slug}")

    tenant = Tenant(
        id=final_slug,
        slug=final_slug,
        name=name,
        pricing_sheet_id=pricing_sheet_id or settings.pricing_sheet_id or None,
        contact_email=contact_email,
        reply_mode=settings.reply_mode,
        is_active=True,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def tenant_pricing_sheet_id(tenant: Tenant) -> Optional[str]:
    settings = get_settings()
    return tenant.pricing_sheet_id or settings.pricing_sheet_id or None


def tenant_reply_mode(tenant: Tenant) -> str:
    return tenant.reply_mode or get_settings().reply_mode
