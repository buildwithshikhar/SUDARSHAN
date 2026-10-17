from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    COOKIE_NAME,
    Principal,
    current_principal,
    get_db,
    issue_session,
    require_csrf,
)
from app.config import Settings
from app.models import User
from app.security import hash_password, verify_password
from app.users import UserError, validate_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Verified against when the account does not exist, so timing does not reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-account-password")
_INVALID = "Invalid email or password"


class LoginBody(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    language: str
    theme: str


class SessionOut(BaseModel):
    user: UserOut
    csrf: str
    expiresAt: datetime  # noqa: N815


class PreferencesBody(BaseModel):
    language: Literal["en", "hi"] | None = None
    theme: Literal["dark", "light"] | None = None


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        language=user.language,
        theme=user.theme,
    )


def _client_key(request: Request) -> str:
    return f"ip:{request.client.host if request.client else 'unknown'}"


@router.post("/login")
def login(
    body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionOut:
    settings: Settings = request.app.state.settings
    limiter = request.app.state.rate_limiter
    try:
        email = validate_email(body.email)
    except UserError:
        email = body.email.strip().lower()[:320]
    keys = (_client_key(request), f"acct:{email}")

    wait = limiter.retry_after(*keys)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = db.query(User).filter(User.email == email).one_or_none()
    stored_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(stored_hash, body.password)
    if user is None or not password_ok or (settings.is_production and user.is_demo):
        limiter.record_failure(*keys)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID)

    limiter.reset(*keys)
    token, record = issue_session(db, user, settings)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_is_secure,
        path="/",
    )
    return SessionOut(user=user_out(user), csrf=record.csrf_token, expiresAt=record.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    db.delete(principal.session)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(principal: Principal = Depends(current_principal)) -> SessionOut:
    return SessionOut(
        user=user_out(principal.user),
        csrf=principal.session.csrf_token,
        expiresAt=principal.session.expires_at,
    )


@router.patch("/me/preferences")
def update_preferences(
    body: PreferencesBody,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    user = principal.user
    if body.language is not None:
        user.language = body.language
    if body.theme is not None:
        user.theme = body.theme
    db.add(user)
    db.commit()
    return user_out(user)
