"""FastAPI auth dependencies."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt_tokens import get_user_id_from_token
from app.db.models import Tenant, User, get_db
from app.tenants.service import resolve_tenant

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user_id = get_user_id_from_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def get_user_from_token_param(token: str, db: Session) -> User:
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_tenant_access(db: Session, user: User, tenant_key: str) -> Tenant:
    tenant = resolve_tenant(db, tenant_key)
    if tenant.owner_user_id is not None and tenant.owner_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this company")
    return tenant
