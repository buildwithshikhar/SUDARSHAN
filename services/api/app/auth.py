"""Sessions, CSRF and role guards."""

import hashlib
import secrets
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Role, SessionRecord, User

COOKIE_NAME = "session"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def issue_session(db: Session, user: User, settings: Settings) -> tuple[str, SessionRecord]:
    """Create a session; returns the cookie token (never stored) and the stored record."""
    now = datetime.now(UTC)
    db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= now))
    token = secrets.token_urlsafe(32)
    record = SessionRecord(
        id=hash_token(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(record)
    db.commit()
    return token, record


@dataclass(frozen=True)
class Principal:
    user: User
    session: SessionRecord


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = request.cookies.get(COOKIE_NAME)
    unauthorised = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    if not token:
        raise unauthorised
    record = db.get(SessionRecord, hash_token(token))
    if record is None:
        raise unauthorised
    if _as_utc(record.expires_at) <= datetime.now(UTC):
        db.delete(record)
        db.commit()
        raise unauthorised
    user = db.get(User, record.user_id)
    if user is None:
        raise unauthorised
    return Principal(user, record)


def require_csrf(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    """Authenticated and, for unsafe methods, carrying the session's CSRF token."""
    if request.method in UNSAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not secrets.compare_digest(supplied, principal.session.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    return principal


def require_roles(*roles: Role) -> Callable[..., Principal]:
    allowed = frozenset(roles)

    def dependency(principal: Principal = Depends(require_csrf)) -> Principal:
        if principal.user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted for this role")
        return principal

    return dependency


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at, User.email)))
