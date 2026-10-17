from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_db, list_users, require_roles
from app.models import Role

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserRow(BaseModel):
    id: str
    email: str
    role: str
    isDemo: bool  # noqa: N815
    createdAt: datetime  # noqa: N815


@router.get("", dependencies=[Depends(require_roles(Role.admin))])
def users(db: Session = Depends(get_db)) -> list[UserRow]:
    return [
        UserRow(id=u.id, email=u.email, role=u.role.value, isDemo=u.is_demo, createdAt=u.created_at)
        for u in list_users(db)
    ]
