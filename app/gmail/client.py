"""Build Gmail API service from tenant credentials."""

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.auth.google_oauth import load_credentials


def get_gmail_service(db: Session, tenant_id: str):
    creds = load_credentials(db, tenant_id)
    if not creds:
        raise RuntimeError(f"No Google credentials for tenant {tenant_id}")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)
