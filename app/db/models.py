"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """One row per moving company — data isolated by tenant_id in all other tables."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    connected_gmail_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gmail_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    pricing_sheet_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    rules_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reply_mode: Mapped[str] = mapped_column(String(16), default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    oauth_tokens: Mapped[list["OAuthToken"]] = relationship(back_populates="tenant")
    message_logs: Mapped[list["MessageLog"]] = relationship(back_populates="tenant")
    scheduled_jobs: Mapped[list["ScheduledJobRecord"]] = relationship(back_populates="tenant")
    processed_threads: Mapped[list["ProcessedThread"]] = relationship(back_populates="tenant")
    owner: Mapped[Optional["User"]] = relationship(back_populates="tenants")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenants: Mapped[list["Tenant"]] = relationship(back_populates="owner")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="google")
    token_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="oauth_tokens")


class ProcessedThread(Base):
    """Tracks Gmail threads we've already handled."""

    __tablename__ = "processed_threads"
    __table_args__ = (UniqueConstraint("tenant_id", "gmail_thread_id", name="uq_tenant_thread"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(128))
    last_message_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="processed")
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="processed_threads")


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    gmail_thread_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    gmail_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    gmail_draft_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    direction: Mapped[str] = mapped_column(String(16))  # inbound | outbound | draft | reminder | followup
    subject: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    extraction_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quote_amount: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reply_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="message_logs")


class ScheduledJobRecord(Base):
    """Booked jobs for reminders (synced from Google Sheet or manual entry)."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_tenant_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))  # sheet row id or calendar event id
    source: Mapped[str] = mapped_column(String(32))  # sheet | calendar | manual
    customer_email: Mapped[str] = mapped_column(String(255))
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    move_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # YYYY-MM-DD
    job_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    load_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    confirmation_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="scheduled_jobs")


class ReminderLog(Base):
    """Idempotency: which reminders were already sent."""

    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_id", "days_before", name="uq_reminder"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[int] = mapped_column(Integer)
    days_before: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FollowupLog(Base):
    __tablename__ = "followup_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(128))
    attempt: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tokens_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite(engine)


def _migrate_sqlite(engine) -> None:
    """Add new tenant columns on existing SQLite DBs."""
    if not str(engine.url).startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "tenants" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("tenants")}
    alters = {
        "slug": "VARCHAR(64)",
        "owner_user_id": "INTEGER",
        "contact_email": "VARCHAR(255)",
        "connected_gmail_email": "VARCHAR(255)",
        "rules_file": "VARCHAR(255)",
        "reply_mode": "VARCHAR(16) DEFAULT 'draft'",
        "is_active": "BOOLEAN DEFAULT 1",
    }
    with engine.begin() as conn:
        for col, typedef in alters.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col} {typedef}"))
        conn.execute(text("UPDATE tenants SET slug = id WHERE slug IS NULL OR slug = ''"))
        conn.execute(text("UPDATE tenants SET is_active = 1 WHERE is_active IS NULL"))
        conn.execute(text("UPDATE tenants SET reply_mode = 'draft' WHERE reply_mode IS NULL OR reply_mode = ''"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
