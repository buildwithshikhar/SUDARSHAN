import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(enum.StrEnum):
    trainee = "trainee"
    instructor = "instructor"
    admin = "admin"


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role", native_enum=False, length=16))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(2), default="en", server_default="en")
    theme: Mapped[str] = mapped_column(String(8), default="dark", server_default="dark")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SessionRecord(Base):
    """A sign-in session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrainingSession(Base):
    """One live training session: who played which scenario, how it ended, and the stored record.

    `record` is the `session-record.v1` JSON of the whole session (inputs and event chain), written
    when the session ends; `event_head`, `event_count` and `final_state_hash` are kept beside it so
    the chain can be checked against values outside the JSON (docs/LIVE_SESSION.md).
    """

    __tablename__ = "training_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(64))
    scenario_version: Mapped[str] = mapped_column(String(32))
    seed: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="lobby")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticks: Mapped[int] = mapped_column(Integer, default=0)
    final_state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_head: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    record: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The `score-result.v1` JSON, written when a session ends (docs/SCORING.md); it records the
    #: rule-pack and scenario versions it was computed with, so it stays as it was scored.
    score: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScenarioRecord(Base):
    """A scenario kept beyond the shipped packs: authored in the editor or generated and saved.

    `spec` is the `scenario.v1` JSON and `spec_sha256` the hash of its canonical form, so a kept
    scenario can be checked against what was generated. A generated one also keeps the request,
    the share code and every check result; the session catalogue looks a scenario up here after
    the packs, so it plays, replays and scores like any other (docs/SCENARIO_ENGINE.md).
    """

    __tablename__ = "scenario_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    origin: Mapped[str] = mapped_column(String(16))
    spec: Mapped[str] = mapped_column(Text)
    spec_sha256: Mapped[str] = mapped_column(String(64))
    yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    request: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    checks: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
