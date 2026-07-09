"""Multi-tenant helpers — each company is an isolated row in shared tables."""

import re
from typing import Optional

from sqlalchemy.orm import Session

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


def list_tenants_for_user(db: Session, user_id: int, active_only: bool = True) -> list[Tenant]:
    q = db.query(Tenant).filter(Tenant.owner_user_id == user_id).order_by(Tenant.name)
    if active_only:
        q = q.filter(Tenant.is_active.is_(True))
    return q.all()


def tenant_to_dict(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "gmail_connected": tenant.gmail_connected,
        "connected_gmail_email": tenant.connected_gmail_email,
        "pricing_sheet_id": tenant.pricing_sheet_id,
        "is_active": tenant.is_active,
        "reply_mode": tenant.reply_mode,
    }


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
    owner_user_id: Optional[int] = None,
) -> Tenant:
    from app.config import get_settings

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
        owner_user_id=owner_user_id,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def assign_orphan_tenants_to_user(db: Session, user_id: int) -> int:
    orphans = db.query(Tenant).filter(Tenant.owner_user_id.is_(None)).all()
    for tenant in orphans:
        tenant.owner_user_id = user_id
    if orphans:
        db.commit()
    return len(orphans)


def tenant_pricing_sheet_id(tenant: Tenant) -> Optional[str]:
    from app.config import get_settings

    settings = get_settings()
    return tenant.pricing_sheet_id or settings.pricing_sheet_id or None


def tenant_reply_mode(tenant: Tenant) -> str:
    from app.config import get_settings

    return tenant.reply_mode or get_settings().reply_mode
