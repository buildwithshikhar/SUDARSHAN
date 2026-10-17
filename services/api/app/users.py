import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password

MIN_ADMIN_PASSWORD_LENGTH = 12
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserError(ValueError):
    """A user operation was rejected; the message is safe to show."""


@dataclass(frozen=True)
class CreateResult:
    user: User
    created: bool


def validate_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not _EMAIL.match(cleaned):
        raise UserError("email address is not valid")
    return cleaned


def create_admin(session: Session, email: str, password: str) -> CreateResult:
    """Create the administrator, or report that it already exists. Safe to repeat."""
    cleaned = validate_email(email)
    existing = session.scalar(select(User).where(User.email == cleaned))
    if existing is not None:
        if existing.role is not Role.admin:
            raise UserError(f"{cleaned} exists with role {existing.role.value}, not admin")
        return CreateResult(existing, created=False)
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise UserError(f"password must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters")
    user = User(email=cleaned, password_hash=hash_password(password), role=Role.admin)
    session.add(user)
    session.commit()
    return CreateResult(user, created=True)


def upsert_demo_user(session: Session, email: str, role: Role, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, role=role, password_hash=hash_password(password), is_demo=True)
        session.add(user)
    else:
        user.password_hash = hash_password(password)
        user.role = role
        user.is_demo = True
    session.commit()
    return user
