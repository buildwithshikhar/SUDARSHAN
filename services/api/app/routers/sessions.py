"""Training sessions: the REST API and the live WebSocket (docs/LIVE_SESSION.md)."""

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, Principal, get_db, require_csrf, require_roles, resolve_principal
from app.contracts import EventRecord, SessionRecord
from app.live import wire
from app.live.manager import (
    CLOSE_FORBIDDEN,
    CLOSE_NOT_FOUND,
    CLOSE_UNAUTHENTICATED,
    Connection,
    LiveSession,
    Refused,
    SessionInfo,
    SessionManager,
)
from app.models import Role, TrainingSession
from app.scoring import score_session
from sim import replay
from sim.audience import trainee_event
from sim.eventlog import verify

log = logging.getLogger("app.live")

router = APIRouter(prefix="/api/v1", tags=["sessions"])

PLAYERS = (Role.trainee, Role.instructor)
PLAYER = require_roles(*PLAYERS)
ADMIN = require_roles(Role.admin)
#: Statuses of a session that has not finished.
UNFINISHED = ("lobby", "running")


def manager_of(request: Request) -> SessionManager:
    manager: SessionManager = request.app.state.live
    return manager


# ----------------------------------------------------------------------------- scenarios


class ScenarioOut(BaseModel):
    id: str
    version: str
    title: dict[str, str]
    summary: dict[str, str]
    duration_s: float
    default_seed: int
    start_time_of_day_h: float
    weather_condition: str
    #: The scenario as a trainee is briefed (never the threats) and the rule pack it names.
    briefing: dict[str, Any]
    rule_pack: dict[str, Any]


@router.get("/scenarios", dependencies=[Depends(PLAYER)])
def scenarios(request: Request) -> list[ScenarioOut]:
    out: list[ScenarioOut] = []
    for entry in manager_of(request).catalog.all_entries().values():
        spec = entry.spec
        if spec.meta is not None and not spec.meta.playable:
            continue
        out.append(
            ScenarioOut(
                id=spec.id,
                version=spec.version,
                title=spec.title.model_dump(),
                summary=spec.summary.model_dump(),
                duration_s=spec.duration_s,
                default_seed=spec.default_seed,
                start_time_of_day_h=spec.world.start_time_of_day_h,
                weather_condition=spec.world.weather.condition,
                briefing=wire.briefing(spec, entry.modalities),
                rule_pack={
                    "id": entry.engine.pack.id,
                    "version": entry.engine.pack.version,
                    "title": entry.engine.pack.title.model_dump(),
                },
            )
        )
    return sorted(out, key=lambda s: s.id)


# ----------------------------------------------------------------------------- sessions


class SessionOut(BaseModel):
    id: str
    scenario_id: str
    scenario_version: str
    seed: int
    status: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    ticks: int


class CreateBody(BaseModel):
    scenario_id: str = Field(max_length=64)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)


def _out(row: TrainingSession, manager: SessionManager) -> SessionOut:
    live = manager.sessions.get(row.id)
    ticks = live.world.tick if live is not None and live.world is not None else row.ticks
    return SessionOut(
        id=row.id,
        scenario_id=row.scenario_id,
        scenario_version=row.scenario_version,
        seed=row.seed,
        status=row.status,
        created_at=row.created_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        ticks=ticks,
    )


def _owned(db: Session, session_id: str, principal: Principal) -> TrainingSession:
    row = db.get(TrainingSession, session_id)
    if row is None or row.user_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such session")
    return row


def _create(request: Request, user_id: str, body: CreateBody) -> SessionOut:
    manager = manager_of(request)
    entry = manager.catalog.get(body.scenario_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such scenario")
    if entry.spec.meta is not None and not entry.spec.meta.playable:
        raise HTTPException(status.HTTP_409_CONFLICT, "This scenario is not playable")
    seed = entry.spec.default_seed if body.seed is None else body.seed
    with manager.session_factory() as db:
        db.execute(
            update(TrainingSession)
            .where(TrainingSession.user_id == user_id, TrainingSession.status.in_(UNFINISHED))
            .values(status="abandoned", ended_at=datetime.now(UTC))
        )
        row = TrainingSession(
            user_id=user_id,
            scenario_id=entry.spec.id,
            scenario_version=entry.spec.version,
            seed=seed,
            status="lobby",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _out(row, manager)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateBody, request: Request, principal: Principal = Depends(PLAYER)
) -> SessionOut:
    # A live session of this user is stored and closed first; the rest are only marked.
    await manager_of(request).abandon_user(principal.user.id)
    return await run_in_threadpool(_create, request, principal.user.id, body)


@router.get("/sessions", dependencies=[Depends(PLAYER)])
def list_sessions(
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    rows = db.scalars(
        select(TrainingSession)
        .where(TrainingSession.user_id == principal.user.id)
        .order_by(TrainingSession.created_at.desc(), TrainingSession.id)
    )
    manager = manager_of(request)
    return [_out(row, manager) for row in rows]


@router.get("/sessions/stats", dependencies=[Depends(ADMIN)])
def session_stats(request: Request) -> dict[str, Any]:
    return manager_of(request).stats()


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SessionOut:
    return _out(_owned(db, session_id, principal), manager_of(request))


@router.get("/sessions/{session_id}/log")
def session_log(
    session_id: str,
    request: Request,
    deep: bool = Query(default=False),
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """The stored event log, verified on read. A trainee gets the trainee projection."""
    row = _owned(db, session_id, principal)
    if row.record is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The session has not ended yet")
    data: Any = None
    try:
        data = json.loads(row.record)
        stored = data["events"]
        if not isinstance(stored, list):
            raise TypeError("events")
    except (ValueError, KeyError, TypeError):
        stored = []
    bad = verify(stored, row.event_head) if stored else 0
    out: dict[str, Any] = {
        "verified": bad is None,
        "first_bad_seq": bad,
        "event_count": row.event_count,
        "head": row.event_head,
        "final_state_hash": row.final_state_hash,
    }
    if principal.user.role is Role.trainee:
        events: list[Any] = []
        for item in stored:
            with contextlib.suppress(ValidationError):
                projected = trainee_event(EventRecord.model_validate(item))
                if projected is not None:
                    events.append(projected)
        out["events"] = events
    else:
        out["events"] = stored
    if deep:
        out.update(_deep_replay(request, row, data if stored else None))
    return out


@router.get("/sessions/{session_id}/score")
def session_score(
    session_id: str,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """The scored debrief of an ended session. It names the real class of each contact, so it is
    given only once the session has ended. A score is stored when the session ends; an older ended
    session is scored here from its stored record and kept."""
    row = _owned(db, session_id, principal)
    if row.status != "ended" or row.record is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an ended session has a score")
    if row.score is None:
        entry = manager_of(request).catalog.get(row.scenario_id, row.scenario_version)
        if entry is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "The scenario is no longer available")
        record = SessionRecord.model_validate_json(row.record)
        row.score = score_session(entry.spec, entry.engine.pack, record).model_dump_json()
        db.commit()
    scored: dict[str, Any] = json.loads(row.score)
    return scored


def _deep_replay(request: Request, row: TrainingSession, data: Any) -> dict[str, Any]:
    """Re-run the stored inputs and compare; `replay_matches` is `None` when that is impossible."""
    entry = manager_of(request).catalog.get(row.scenario_id, row.scenario_version)
    if entry is None:
        return {"replay_matches": None, "replay_first_divergent_seq": None}
    try:
        record = SessionRecord.model_validate(data)
    except ValidationError:
        return {"replay_matches": False, "replay_first_divergent_seq": None}
    result = replay.replay(entry.spec, record)
    return {
        "replay_matches": result.matches,
        "replay_first_divergent_seq": result.first_divergent_seq,
    }


# ----------------------------------------------------------------------------- live socket


def origin_allowed(origin: str | None, host: str | None, allowed: list[str]) -> bool:
    """The upgrade is a GET carrying the session cookie, so the origin is the CSRF defence.

    A browser always sends `Origin` on a WebSocket; a request without one is not from a page, so it
    cannot be cross-site. Otherwise the origin must be this host or one of `CORS_ORIGINS`.
    """
    if not origin:
        return True
    if origin.rstrip("/") in (a.rstrip("/") for a in allowed):
        return True
    return bool(host) and urlsplit(origin).netloc.lower() == (host or "").lower()


def _admit(
    request_app: Any, token: str | None, session_id: str
) -> tuple[SessionInfo | None, int | None, str]:
    """Who is knocking and may they join: the session, or the close code to refuse with."""
    with request_app.state.session_factory() as db:
        try:
            principal = resolve_principal(db, token)
        except HTTPException:
            return None, CLOSE_UNAUTHENTICATED, "Not signed in"
        if principal.user.role not in PLAYERS:
            return None, CLOSE_FORBIDDEN, "This role cannot play"
        row = db.get(TrainingSession, session_id)
        if row is None:
            return None, CLOSE_NOT_FOUND, "No such session"
        if row.user_id != principal.user.id:
            return None, CLOSE_FORBIDDEN, "Not your session"
        info = SessionInfo(
            row.id, row.user_id, row.scenario_id, row.scenario_version, row.seed, row.status
        )
        if row.status in ("ended", "abandoned"):
            return info, 4409, "The session has ended; read its log"
        return info, None, ""


@router.websocket("/sessions/{session_id}/ws")
async def live_socket(ws: WebSocket, session_id: str) -> None:
    app = ws.app
    settings = app.state.settings
    if not origin_allowed(
        ws.headers.get("origin"), ws.headers.get("host"), settings.cors_origin_list
    ):
        await ws.close(code=1008)  # before accept: the handshake is refused (HTTP 403)
        return
    await ws.accept()
    info, code, reason = await run_in_threadpool(
        _admit, app, ws.cookies.get(COOKIE_NAME), session_id
    )
    if info is None or code is not None:
        await ws.close(code=code or 1011, reason=reason)
        return
    manager: SessionManager = app.state.live
    try:
        live, conn = await manager.attach(ws, info)
    except Refused as refusal:
        await ws.close(code=refusal.code, reason=refusal.message)
        return
    except Exception:
        log.exception("could not attach to session %s", session_id)
        await ws.close(code=1011)
        return
    reader = asyncio.ensure_future(_pump(ws, live, conn))
    try:
        await asyncio.wait({reader, conn.writer}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        reader.cancel()
        live.detach(conn)
        conn.writer.cancel()


async def _pump(ws: WebSocket, live: LiveSession, conn: Connection) -> None:
    """Read the client's frames until it goes away."""
    with contextlib.suppress(RuntimeError):
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            data = message.get("bytes")
            if data is None:
                conn.send(wire.pack(wire.fault("invalid", "Binary frames only.")))
                conn.close(1003)
            else:
                live.on_message(conn, data)
