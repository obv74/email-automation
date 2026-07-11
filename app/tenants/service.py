"""Multi-tenant helpers — each company is an isolated row in shared tables."""

import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Tenant


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:48] or "company"


def pricing_sheet_url(sheet_id: Optional[str]) -> Optional[str]:
    if not sheet_id:
        return None
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


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
    from app.config import get_settings
    from app.prompts.defaults import (
        CLASSIFY_PLACEHOLDERS,
        CLASSIFY_PROMPT,
        EXTRACTION_PLACEHOLDERS,
        EXTRACTION_SYSTEM,
        EXTRACTION_USER,
        REPLY_PLACEHOLDERS,
        REPLY_TEMPLATE,
    )

    settings = get_settings()
    sheet_id = tenant.pricing_sheet_id or settings.pricing_sheet_id or None
    classify = (tenant.classify_prompt or "").strip() or CLASSIFY_PROMPT
    extraction_system = (tenant.extraction_system_prompt or "").strip() or EXTRACTION_SYSTEM
    extraction_user = (tenant.extraction_user_prompt or "").strip() or EXTRACTION_USER
    reply = (tenant.reply_template or "").strip() or REPLY_TEMPLATE
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "gmail_connected": tenant.gmail_connected,
        "connected_gmail_email": tenant.connected_gmail_email,
        "pricing_sheet_id": sheet_id,
        "pricing_sheet_url": pricing_sheet_url(sheet_id),
        "is_active": tenant.is_active,
        "reply_mode": tenant.reply_mode or settings.reply_mode,
        "ai_enabled": True if tenant.ai_enabled is None else bool(tenant.ai_enabled),
        "poll_interval_minutes": tenant.poll_interval_minutes or settings.poll_gmail_interval_minutes,
        "classify_prompt": classify,
        "extraction_system_prompt": extraction_system,
        "extraction_user_prompt": extraction_user,
        "reply_template": reply,
        "prompt_placeholders": {
            "classify": CLASSIFY_PLACEHOLDERS,
            "extraction": EXTRACTION_PLACEHOLDERS,
            "reply": REPLY_PLACEHOLDERS,
        },
        "using_default_prompts": {
            "classify": not bool((tenant.classify_prompt or "").strip()),
            "extraction_system": not bool((tenant.extraction_system_prompt or "").strip()),
            "extraction_user": not bool((tenant.extraction_user_prompt or "").strip()),
            "reply": not bool((tenant.reply_template or "").strip()),
        },
    }


def get_or_create_user_company(
    db: Session,
    user_id: int,
    user_name: str,
    user_email: str,
) -> Tenant:
    tenants = list_tenants_for_user(db, user_id)
    if tenants:
        return tenants[0]
    return create_tenant(
        db,
        name=user_name or "My Moving Company",
        slug=slugify(f"company-{user_id}"),
        contact_email=user_email,
        owner_user_id=user_id,
    )


def tenant_poll_interval_minutes(tenant: Tenant) -> int:
    from app.config import get_settings

    return tenant.poll_interval_minutes or get_settings().poll_gmail_interval_minutes


def tenant_due_for_poll(tenant: Tenant) -> bool:
    if not tenant.last_polled_at:
        return True
    interval = tenant_poll_interval_minutes(tenant)
    return datetime.utcnow() - tenant.last_polled_at >= timedelta(minutes=interval)


def mark_tenant_polled(db: Session, tenant: Tenant) -> None:
    tenant.last_polled_at = datetime.utcnow()
    db.commit()


def list_pollable_tenants(db: Session) -> list[Tenant]:
    """Only active tenants with Gmail connected and AI enabled."""
    return (
        db.query(Tenant)
        .filter(
            Tenant.is_active.is_(True),
            Tenant.gmail_connected.is_(True),
            Tenant.ai_enabled.is_(True),
        )
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
        ai_enabled=True,
        is_active=True,
        owner_user_id=owner_user_id,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update_tenant_settings(
    db: Session,
    tenant: Tenant,
    *,
    name: Optional[str] = None,
    pricing_sheet_id: Optional[str] = None,
    reply_mode: Optional[str] = None,
    poll_interval_minutes: Optional[int] = None,
    ai_enabled: Optional[bool] = None,
    classify_prompt: Optional[str] = None,
    extraction_system_prompt: Optional[str] = None,
    extraction_user_prompt: Optional[str] = None,
    reply_template: Optional[str] = None,
    reset_prompts: Optional[bool] = None,
) -> Tenant:
    if name is not None:
        tenant.name = name.strip()
    if pricing_sheet_id is not None:
        tenant.pricing_sheet_id = pricing_sheet_id.strip() or None
    if reply_mode is not None:
        if reply_mode not in ("draft", "send"):
            raise ValueError("reply_mode must be draft or send")
        tenant.reply_mode = reply_mode
    if poll_interval_minutes is not None:
        if poll_interval_minutes < 1 or poll_interval_minutes > 1440:
            raise ValueError("poll_interval_minutes must be between 1 and 1440")
        tenant.poll_interval_minutes = poll_interval_minutes
    if ai_enabled is not None:
        tenant.ai_enabled = ai_enabled
    if reset_prompts:
        tenant.classify_prompt = None
        tenant.extraction_system_prompt = None
        tenant.extraction_user_prompt = None
        tenant.reply_template = None
    else:
        from app.prompts.defaults import (
            CLASSIFY_PROMPT,
            EXTRACTION_SYSTEM,
            EXTRACTION_USER,
            REPLY_TEMPLATE,
        )

        def _store_or_default(value: Optional[str], default: str) -> Optional[str]:
            if value is None:
                return None  # field not sent — caller shouldn't pass None meaning "clear" for partial updates
            text = value.strip()
            if not text or text == default.strip():
                return None
            return text

        if classify_prompt is not None:
            tenant.classify_prompt = _store_or_default(classify_prompt, CLASSIFY_PROMPT)
        if extraction_system_prompt is not None:
            tenant.extraction_system_prompt = _store_or_default(
                extraction_system_prompt, EXTRACTION_SYSTEM
            )
        if extraction_user_prompt is not None:
            tenant.extraction_user_prompt = _store_or_default(extraction_user_prompt, EXTRACTION_USER)
        if reply_template is not None:
            tenant.reply_template = _store_or_default(reply_template, REPLY_TEMPLATE)
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
