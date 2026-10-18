"""Live sessions: one asyncio task per session ticking the simulation at 20 Hz.

All of it runs in the event loop of one API worker. A tick costs well under a millisecond with the
sensors, tracker and rules, so steps run directly in the loop; only database writes and building
the world (loading profiles) go to a thread. Ticks are scheduled against a monotonic clock (tick
*n* of a run is due at start + n x 0.05 s), so a slow tick is followed by a quicker one. Simulation
time never depends on wall time: the clock only decides when the next `World.step` is called.

A session ticks only while a client is connected. A disconnect pauses it (no ticks, nothing in the
log) and it is stored as abandoned if the trainee does not return within the grace period.
"""

import asyncio
import contextlib
import logging
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from fastapi import WebSocket
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.contracts import TICK_HZ, ActionRecord, SessionRecord
from app.contracts.common import PackRef
from app.contracts.live import ACTION_KEYS, Act, LiveClientMessage
from app.models import TrainingSession
from app.scoring import score_session
from sim import replay
from sim.eventlog import verify
from sim.tracking.picture import Picture
from sim.world import World

from . import wire
from .catalog import CatalogEntry, ScenarioCatalog

log = logging.getLogger("app.live")

DT = 1.0 / TICK_HZ
#: Behind by more than this (s) and the loop drops the lag instead of running ticks flat out.
LAG_LIMIT_S = 0.5
#: Frames queued for a slow client before new ones are dropped for it.
MAX_QUEUED_FRAMES = 100
#: Close codes (docs/LIVE_SESSION.md).
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_SUPERSEDED = 4408
CLOSE_ENDED = 4409
CLOSE_TOO_LARGE = 4413
CLOSE_FULL = 1013
_SAMPLES = 200_000


class Refused(Exception):
    """A connection that cannot be attached; `code` is the WebSocket close code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SessionInfo:
    """What the manager needs to know about a stored session to run it."""

    id: str
    user_id: str
    scenario_id: str
    scenario_version: str
    seed: int
    status: str


def percentiles(samples: deque[float] | list[float]) -> dict[str, float | int]:
    """Nearest-rank p50, p95, p99 and the maximum of `samples`, rounded to 3 decimals."""
    ordered = sorted(samples)
    if not ordered:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    def at(p: float) -> float:
        return round(ordered[max(0, math.ceil(p * len(ordered)) - 1)], 3)

    return {
        "count": len(ordered),
        "p50": at(0.50),
        "p95": at(0.95),
        "p99": at(0.99),
        "max": at(1.0),
    }


class Connection:
    """One WebSocket with its own outgoing queue, so a slow client never stalls a session's tick."""

    def __init__(self, ws: WebSocket, user_id: str) -> None:
        self.ws = ws
        self.user_id = user_id
        self._queue: asyncio.Queue[bytes | int] = asyncio.Queue()
        self.writer: asyncio.Task[None] = asyncio.create_task(self._write())

    def congested(self) -> bool:
        """True when this client is too far behind to be sent another frame."""
        return self._queue.qsize() >= MAX_QUEUED_FRAMES

    def send(self, data: bytes) -> None:
        self._queue.put_nowait(data)

    def close(self, code: int = 1000) -> None:
        """Close after everything already queued has been sent."""
        self._queue.put_nowait(code)

    async def _write(self) -> None:
        try:
            while True:
                item = await self._queue.get()
                if isinstance(item, int):
                    await self.ws.close(code=item)
                    return
                await self.ws.send_bytes(item)
        except Exception:  # noqa: BLE001 - the peer is gone; the reader notices and detaches
            return


class LiveSession:
    def __init__(self, manager: "SessionManager", info: SessionInfo, entry: CatalogEntry) -> None:
        self.manager = manager
        self.info = info
        self.entry = entry
        self.status = "lobby"
        self.world: World | None = None
        self.conn: Connection | None = None
        self.actions: list[ActionRecord] = []
        self.pending: list[ActionRecord] = []
        self.task: asyncio.Task[None] | None = None
        self.done = asyncio.Event()
        self.total_ticks = round(entry.spec.duration_s * TICK_HZ)
        self._wake = asyncio.Event()
        self._build = asyncio.Lock()
        self._end: str | None = None
        self._sent = 0
        self._lost_at = manager.clock()
        self._anchor: tuple[float, int] | None = None
        self._marked_started = False
        self._tokens = float(manager.act_rate)
        self._token_time = manager.clock()

    # ------------------------------------------------------------------ joining and leaving

    async def ensure_world(self) -> World:
        async with self._build:
            if self.world is None:
                self.world = await asyncio.to_thread(self._make_world)
            return self.world

    def _make_world(self) -> World:
        spec, seed = self.entry.spec, self.info.seed
        return World(spec, seed, picture=Picture.build(spec, seed), roe=self.entry.engine)

    def attach(self, conn: Connection) -> None:
        """Make `conn` the session's client; an earlier one is superseded (close 4408)."""
        old, self.conn = self.conn, conn
        if old is not None:
            old.send(wire.pack(wire.fault("superseded", "Another connection took this session.")))
            old.close(CLOSE_SUPERSEDED)
        assert self.world is not None
        conn.send(wire.pack(wire.welcome(self.info.id, self.status, self.world, self.entry.engine)))
        # The join frame repeats every trainee event so far, so a reconnecting console is whole.
        conn.send(wire.pack(wire.frame(self.world, self.status, self.world.log.records)))
        self._sent = len(self.world.log)
        if self.task is None:
            self.task = asyncio.create_task(self._main(), name=f"live-{self.info.id}")
        self._wake.set()

    def detach(self, conn: Connection) -> None:
        if self.conn is conn:
            self.conn = None
            self._lost_at = self.manager.clock()
            self._anchor = None
            self._wake.set()

    # ------------------------------------------------------------------ client messages

    def on_message(self, conn: Connection, data: bytes) -> None:
        """Handle one binary frame from the client. Refusals are sent to `conn`."""
        if conn is not self.conn:
            return
        if len(data) > wire.MAX_CLIENT_FRAME:
            self._refuse(conn, "too-large", "Message over 16 KiB.", CLOSE_TOO_LARGE)
            return
        try:
            obj = wire.unpack(data)
        except ValueError:
            self._refuse(conn, "invalid", "Not a MessagePack message.", 1007)
            return
        kind = obj.get("t") if isinstance(obj, dict) else None
        if not isinstance(kind, str):
            self._refuse(conn, "invalid", "A message is a map with a t field.", 1007)
        elif kind == "act":
            self._on_act(conn, obj)
        else:
            try:
                message = LiveClientMessage.model_validate(obj).root
            except ValidationError:
                self._refuse(conn, "invalid", f"Malformed {kind!r} message.", 1007)
                return
            if message.t == "ping":
                conn.send(wire.pack({"t": "pong", "ts": message.ts, "tick": self._tick()}))
            elif message.t == "start":
                self._on_start(conn)
            elif message.t == "end":
                if self.status == "running":
                    self._end = "ended"
                    self._wake.set()
                else:
                    conn.send(wire.pack(wire.fault("not-running", "The session is not running.")))
            elif message.t == "leave":
                self.detach(conn)
                conn.close(1000)

    @staticmethod
    def _refuse(conn: Connection, code: str, message: str, close: int) -> None:
        conn.send(wire.pack(wire.fault(code, message)))
        conn.close(close)

    def _tick(self) -> int:
        return self.world.tick if self.world is not None else 0

    def _on_start(self, conn: Connection) -> None:
        if self.status == "lobby":
            self.status = "running"
            self.manager.started += 1
            self._wake.set()
        conn.send(wire.pack({"t": "status", "status": self.status, "tick": self._tick()}))

    def _on_act(self, conn: Connection, obj: dict[Any, Any]) -> None:
        seq = obj.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq <= 2**31:
            self._refuse(conn, "invalid", "act needs an integer seq.", 1007)
            return

        def refuse(code: str, message: str) -> None:
            conn.send(wire.pack(wire.ack(seq, self._tick(), error=(code, message))))

        if not self._take_token():
            refuse("too-many", "Too many actions; slow down.")
            return
        action = obj.get("action")
        if not isinstance(action, str) or action not in ACTION_KEYS:
            refuse("unknown-action", "Unknown action.")
            return
        try:
            act = Act.model_validate(obj)
        except ValidationError:
            refuse("invalid", "Malformed act message.")
            return
        if self.status != "running" or self.world is None:
            refuse("not-running", "The session is not running.")
            return
        problem = wire.check_payload(act.action, act.payload)
        if problem is not None:
            refuse("invalid", problem)
            return
        # The server stamps the tick and the actor; the client's word about either is never used.
        record = ActionRecord(
            tick=self.world.tick,
            actor=f"trainee:{self.info.user_id}",
            action=act.action,
            payload=dict(act.payload),
        )
        self.pending.append(record)
        conn.send(wire.pack(wire.ack(seq, record.tick)))

    def _take_token(self) -> bool:
        now = self.manager.clock()
        rate = float(self.manager.act_rate)
        self._tokens = min(rate, self._tokens + (now - self._token_time) * rate)
        self._token_time = now
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True

    # ------------------------------------------------------------------ the loop

    def request_end(self, status: str) -> None:
        self._end = self._end or status
        self._wake.set()

    async def _wait(self, timeout: float | None) -> None:
        """Sleep until `timeout` seconds pass or something changes (a client, a start, an end)."""
        self._wake.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._wake.wait(), timeout)

    async def _main(self) -> None:
        manager = self.manager
        try:
            while True:
                if self._end is not None:
                    await self._finish(self._end)
                    return
                now = manager.clock()
                if self.conn is None:
                    remaining = self._lost_at + manager.grace_s - now
                    if remaining <= 0:
                        await self._finish("abandoned")
                        return
                    await self._wait(remaining)
                    continue
                if self.status != "running":
                    await self._wait(None)
                    continue
                if not self._marked_started:
                    self._marked_started = True
                    await asyncio.to_thread(manager.mark_started, self.info.id)
                    continue
                assert self.world is not None
                if self._anchor is None:
                    self._anchor = (now, self.world.tick)
                base, first = self._anchor
                due = base + (self.world.tick - first) * DT / manager.speed
                if due > now:
                    await self._wait(due - now)
                    if manager.clock() < due:  # woken early: look at the new state first
                        continue
                    now = manager.clock()
                late = now - due
                if late > LAG_LIMIT_S:
                    manager.lag_drops += 1
                    log.warning(
                        "session %s dropped %.2f s of lag at tick %d",
                        self.info.id,
                        late,
                        self.world.tick,
                    )
                    self._anchor = (now, self.world.tick)
                    late = 0.0
                manager.jitter_ms.append(late * 1000.0)
                self._run_tick()
                if self.world.tick >= self.total_ticks:
                    await self._finish("ended")
                    return
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live session %s failed", self.info.id)
            with contextlib.suppress(Exception):
                await self._finish("abandoned")
        finally:
            manager.sessions.pop(self.info.id, None)
            self.done.set()

    def _run_tick(self) -> None:
        world = self.world
        assert world is not None
        started = perf_counter()
        batch, self.pending = self.pending, []
        self.actions.extend(batch)
        world.step(batch)
        conn = self.conn
        if conn is not None and conn.congested():
            # A slow client skips frames; its events stay unsent and join the next frame.
            self.manager.frames_dropped += 1
        elif conn is not None:
            records = self._new_records()
            conn.send(wire.pack(wire.frame(world, self.status, records)))
            self._sent += len(records)
        self.manager.cost_ms.append((perf_counter() - started) * 1000.0)

    def _new_records(self) -> Any:
        assert self.world is not None
        return self.world.log.records[self._sent :]

    # ------------------------------------------------------------------ ending

    async def _finish(self, status: str) -> None:
        """Close the log, store the record, verify it from the database, then tell the client."""
        world = self.world
        assert world is not None
        final = replay.finish(world)
        self.status = status
        record = SessionRecord(
            contract="session-record.v1",
            scenario=PackRef(id=world.spec.id, version=world.spec.version),
            seed=world.seed,
            ticks=world.tick,
            actions=replay.ordered(self.actions),
            events=list(world.log.records),
            final_state_hash=final,
            picture=True,
            roe=True,
        )
        conn = self.conn
        if conn is not None:
            conn.send(wire.pack(wire.frame(world, status, self._new_records())))
            self._sent = len(world.log)
        verified = False
        try:
            verified = await asyncio.to_thread(self.manager.store, self.info.id, status, record)
        except Exception:
            log.exception("could not store session %s", self.info.id)
        if status == "ended":
            self.manager.completed += 1
        else:
            self.manager.abandoned += 1
        if conn is not None:
            conn.send(
                wire.pack(
                    {
                        "t": "ended",
                        "status": status,
                        "summary": {
                            "ticks": world.tick,
                            "duration_s": world.time_s,
                            "event_count": len(record.events),
                            "head": record.events[-1].hash,
                            "final_state_hash": final,
                            "verified": verified,
                        },
                    }
                )
            )
            conn.close(1000)


class SessionManager:
    """All running sessions of this worker, the metrics, and the stored-session bookkeeping."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        catalog: ScenarioCatalog,
        *,
        grace_s: float = 120.0,
        max_sessions: int = 32,
        act_rate: int = 20,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session_factory = session_factory
        self.catalog = catalog
        self.grace_s = grace_s
        self.max_sessions = max_sessions
        self.act_rate = act_rate
        self.clock = clock
        #: Ticks per wall second, in units of 20 Hz. Always 1.0 in service; tests run faster, which
        #: is safe because simulation time never depends on wall time.
        self.speed = 1.0
        self.sessions: dict[str, LiveSession] = {}
        self.jitter_ms: deque[float] = deque(maxlen=_SAMPLES)
        self.cost_ms: deque[float] = deque(maxlen=_SAMPLES)
        self.lag_drops = 0
        self.frames_dropped = 0
        self.started = 0
        self.completed = 0
        self.abandoned = 0

    # ------------------------------------------------------------------ connections

    async def attach(self, ws: WebSocket, info: SessionInfo) -> tuple[LiveSession, Connection]:
        entry = self.catalog.get(info.scenario_id, info.scenario_version)
        if entry is None:
            raise Refused(CLOSE_NOT_FOUND, "The scenario is no longer available.")
        live = self.sessions.get(info.id)
        if live is None:
            if len(self.sessions) >= self.max_sessions:
                raise Refused(CLOSE_FULL, "The server is full; try again shortly.")
            live = self.sessions[info.id] = LiveSession(self, info, entry)
        try:
            await live.ensure_world()
        except Exception:
            self.sessions.pop(info.id, None)
            raise
        if live._end is not None or live.done.is_set() or live.status in ("ended", "abandoned"):
            raise Refused(CLOSE_ENDED, "The session has ended.")
        conn = Connection(ws, info.user_id)
        live.attach(conn)
        return live, conn

    async def abandon_user(self, user_id: str) -> None:
        """Store and close every live session of `user_id` as abandoned."""
        mine = [s for s in self.sessions.values() if s.info.user_id == user_id]
        for live in mine:
            live.request_end("abandoned")
        for live in mine:
            if live.task is not None:
                await live.done.wait()
            else:  # pragma: no cover - a session without a task has no client yet
                self.sessions.pop(live.info.id, None)

    async def shutdown(self, timeout_s: float = 10.0) -> None:
        """Store every running session as abandoned, close the sockets and stop the tasks."""
        live = list(self.sessions.values())
        for item in live:
            item.request_end("abandoned")
        tasks = [s.task for s in live if s.task is not None]
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=timeout_s)
            for task in pending:  # pragma: no cover - only when the database hangs
                task.cancel()
        for item in live:
            if item.conn is not None:
                item.conn.close(1001)
        self.sessions.clear()

    # ------------------------------------------------------------------ database (threads)

    def mark_started(self, session_id: str) -> None:
        with self.session_factory() as db:
            row = db.get(TrainingSession, session_id)
            if row is not None:
                row.status = "running"
                row.started_at = datetime.now(UTC)
                db.commit()

    def store(self, session_id: str, status: str, record: SessionRecord) -> bool:
        """Write the session record, read it back and verify its hash chain."""
        head = record.events[-1].hash
        with self.session_factory() as db:
            row = db.get(TrainingSession, session_id)
            if row is None:
                return False
            row.status = status
            row.ended_at = datetime.now(UTC)
            row.ticks = record.ticks
            row.final_state_hash = record.final_state_hash
            row.event_head = head
            row.event_count = len(record.events)
            row.record = record.model_dump_json()
            row.score = self._score_json(row, record) if status == "ended" else None
            db.commit()
        with self.session_factory() as db:
            row = db.get(TrainingSession, session_id)
            if row is None or row.record is None:
                return False
            try:
                stored = SessionRecord.model_validate_json(row.record)
            except ValidationError:
                return False
            return (
                verify(stored.events, row.event_head) is None
                and stored.final_state_hash == row.final_state_hash
            )

    def _score_json(self, row: TrainingSession, record: SessionRecord) -> str | None:
        """Score an ended session. A failure to score never loses the session record."""
        entry = self.catalog.get(row.scenario_id, row.scenario_version)
        if entry is None:
            return None
        try:
            return score_session(entry.spec, entry.engine.pack, record).model_dump_json()
        except Exception:  # noqa: BLE001 - the record is stored either way; the score can be redone
            log.exception("could not score session %s", row.id)
            return None

    def abandon_stale(self) -> int:
        """At start-up: sessions left `running` by an earlier process can never resume."""
        with self.session_factory() as db:
            result = db.execute(
                update(TrainingSession)
                .where(TrainingSession.status == "running")
                .values(status="abandoned", ended_at=datetime.now(UTC))
            )
            db.commit()
            return int(result.rowcount)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ metrics

    def stats(self) -> dict[str, Any]:
        live = list(self.sessions.values())
        return {
            "live_sessions": len(live),
            "running": sum(1 for s in live if s.status == "running"),
            "connected": sum(1 for s in live if s.conn is not None),
            "max_live_sessions": self.max_sessions,
            "started_total": self.started,
            "completed_total": self.completed,
            "abandoned_total": self.abandoned,
            "tick_jitter_ms": percentiles(self.jitter_ms),
            "tick_cost_ms": percentiles(self.cost_ms),
            "lag_drops": self.lag_drops,
            "frames_dropped": self.frames_dropped,
        }
