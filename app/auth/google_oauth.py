"""Google OAuth2 flow for Gmail and Sheets."""

import json
import logging
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import OAuthToken, Tenant

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def create_oauth_flow(state: Optional[str] = None) -> Flow:
    settings = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_authorization_url(state: str) -> str:
    flow = create_oauth_flow(state=state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def save_credentials(db: Session, tenant_id: str, credentials: Credentials) -> None:
    token_json = credentials.to_json()
    existing = (
        db.query(OAuthToken)
        .filter(OAuthToken.tenant_id == tenant_id, OAuthToken.provider == "google")
        .first()
    )
    if existing:
        existing.token_json = token_json
    else:
        db.add(OAuthToken(tenant_id=tenant_id, provider="google", token_json=token_json))

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        tenant.gmail_connected = True
    db.commit()


def load_credentials(db: Session, tenant_id: str) -> Optional[Credentials]:
    row = (
        db.query(OAuthToken)
        .filter(OAuthToken.tenant_id == tenant_id, OAuthToken.provider == "google")
        .first()
    )
    if not row:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(row.token_json), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(db, tenant_id, creds)
    return creds


def exchange_code(db: Session, tenant_id: str, authorization_response: str) -> Credentials:
    flow = create_oauth_flow()
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    save_credentials(db, tenant_id, creds)
    return creds
