"""Google OAuth2 flow for Gmail and Sheets."""

import json
import logging
import os
from typing import Optional

from app.config import get_settings

_settings = get_settings()
_redirect = _settings.google_redirect_uri.lower()
if _settings.oauth_allow_insecure_transport or (
    _redirect.startswith("http://")
    and "localhost" not in _redirect
    and "127.0.0.1" not in _redirect
):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.db.models import OAuthToken, Tenant

logger = logging.getLogger(__name__)

# PKCE: keep the same Flow between /connect and /callback (code_verifier must match).
_pending_flows: dict[str, Flow] = {}

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
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
        prompt="consent select_account",
    )
    _pending_flows[state] = flow
    return url


def pop_pending_flow(state: str) -> Optional[Flow]:
    return _pending_flows.pop(state, None)


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
        try:
            from googleapiclient.discovery import build

            gmail = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            profile = gmail.users().getProfile(userId="me").execute()
            tenant.connected_gmail_email = profile.get("emailAddress")
        except Exception as exc:
            logger.warning("Could not read Gmail profile for tenant %s: %s", tenant_id, exc)
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


def exchange_code(
    db: Session,
    tenant_id: str,
    state: str,
    authorization_response: str,
) -> Credentials:
    flow = pop_pending_flow(state)
    if flow is None:
        raise RuntimeError("OAuth session expired. Click Connect Gmail again.")
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    save_credentials(db, tenant_id, creds)
    return creds


def disconnect_gmail(db: Session, tenant_id: str) -> None:
    db.query(OAuthToken).filter(
        OAuthToken.tenant_id == tenant_id,
        OAuthToken.provider == "google",
    ).delete()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        tenant.gmail_connected = False
    db.commit()
