"""API request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: Optional[str]
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreateTenantBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: Optional[str] = None
    pricing_sheet_id: Optional[str] = None
    contact_email: Optional[EmailStr] = None


class TenantOut(BaseModel):
    id: str
    slug: str
    name: str
    gmail_connected: bool
    connected_gmail_email: Optional[str]
    pricing_sheet_id: Optional[str]
    is_active: bool
    reply_mode: str


class MessageLogOut(BaseModel):
    id: int
    direction: str
    subject: Optional[str]
    quote_amount: Optional[str]
    rule_name: Optional[str]
    reply_body: Optional[str]
    gmail_thread_id: Optional[str]
    created_at: datetime
