"""JWT access tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from app.config import get_settings


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])


def get_user_id_from_token(token: str) -> int:
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Invalid token")
        return int(sub)
    except (JWTError, ValueError, TypeError) as exc:
        raise ValueError("Invalid or expired token") from exc
