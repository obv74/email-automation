"""User registration and login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.auth.deps import get_current_user
from app.auth.jwt_tokens import create_access_token
from app.auth.password import hash_password, verify_password
from app.tenants.service import assign_orphan_tenants_to_user
from app.db.models import User, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, created_at=user.created_at)


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    assign_orphan_tenants_to_user(db, user.id)

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=_user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
