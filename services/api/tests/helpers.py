from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.models import Role, User
from app.security import hash_password

PASSWORD = "correct-horse-battery"


def add_user(
    settings: Settings, email: str, role: Role, *, password: str = PASSWORD, is_demo: bool = False
) -> None:
    with Session(make_engine(settings.database_url)) as session:
        session.add(
            User(email=email, password_hash=hash_password(password), role=role, is_demo=is_demo)
        )
        session.commit()
