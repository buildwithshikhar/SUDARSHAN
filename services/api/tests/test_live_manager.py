"""The session manager: pacing, lag, slow clients, failures and shutdown."""

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.db import make_engine, make_session_factory
from app.live import wire
from app.live.catalog import ScenarioCatalog
from app.live.manager import (
    MAX_QUEUED_FRAMES,
    Connection,
    LiveSession,
    SessionInfo,
    SessionManager,
    percentiles,
)
from tests.live_helpers import harrier_world
from tests.live_support import connect, create_session, expect_close, live_app, login


def manager_of(client: TestClient) -> SessionManager:
    manager: SessionManager = client.app.state.live  # type: ignore[attr-defined]
    return manager


def started(client: TestClient) -> dict[str, Any]:
    return create_session(client, login(client))


# ----------------------------------------------------------------------------- statistics


def test_percentiles_use_nearest_rank() -> None:
    assert percentiles([]) == {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    assert percentiles([4.0]) == {"count": 1, "p50": 4.0, "p95": 4.0, "p99": 4.0, "max": 4.0}
    hundred = [float(i) for i in range(100, 0, -1)]
    assert percentiles(hundred) == {
        "count": 100,
        "p50": 50.0,
        "p95": 95.0,
        "p99": 99.0,
        "max": 100.0,
    }


# ----------------------------------------------------------------------------- pacing


def test_ticks_are_paced_at_20_hz(live_client: TestClient) -> None:
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        first = sock.until("frame")
        began = time.monotonic()
        last = sock.frames(30)[-1]  # 30 more ticks should take about 1.5 s
        elapsed = time.monotonic() - began
    assert last["tick"] - first["tick"] == 30
    assert 1.35 < elapsed < 1.9, elapsed
    stats = manager_of(live_client).stats()
    assert stats["tick_jitter_ms"]["p50"] < 10 and stats["tick_jitter_ms"]["max"] < 250
    assert stats["tick_cost_ms"]["max"] < 100 and stats["lag_drops"] == 0


def test_a_clock_jump_drops_the_lag_instead_of_racing_to_catch_up(live_client: TestClient) -> None:
    manager = manager_of(live_client)
    offset = [0.0]
    manager.clock = lambda: time.monotonic() + offset[0]
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        before = sock.frames(5)[-1]["tick"]
        offset[0] += 3.0  # the loop is suddenly three seconds behind
        began = time.monotonic()
        after = sock.frames(10)[-1]["tick"]
        elapsed = time.monotonic() - began
    assert manager.lag_drops == 1
    assert after > before
    assert elapsed > 0.35  # it did not burn through 60 ticks at once: 10 ticks still take ~0.5 s


def test_a_slightly_late_tick_runs_at_once_without_dropping(live_client: TestClient) -> None:
    manager = manager_of(live_client)
    offset = [0.0]
    manager.clock = lambda: time.monotonic() + offset[0]
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(3)
        offset[0] += 0.2  # four ticks behind: all four run back to back
        began = time.monotonic()
        sock.frames(4)
        assert time.monotonic() - began < 0.15
    assert manager.lag_drops == 0


# ----------------------------------------------------------------------------- a slow client


class StubSocket:
    """A WebSocket whose sends block until released."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.sent: list[bytes] = []
        self.closed: int | None = None

    async def send_bytes(self, data: bytes) -> None:
        await self.release.wait()
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = code


def test_a_slow_client_skips_frames_but_loses_no_events(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager = SessionManager(
            make_session_factory(make_engine(f"sqlite:///{tmp_path / 'x.db'}")), ScenarioCatalog()
        )
        entry = manager.catalog.get("harrier-morning-watch")
        assert entry is not None
        info = SessionInfo("s1", "u1", entry.spec.id, entry.spec.version, 5, "lobby")
        live = LiveSession(manager, info, entry)
        live.world = harrier_world(5)
        stub = StubSocket()
        conn = Connection(stub, "u1")  # type: ignore[arg-type]
        live.conn = conn
        live.status = "running"
        await asyncio.sleep(0)
        for _ in range(MAX_QUEUED_FRAMES + 120):
            live._run_tick()
        assert conn.congested()
        assert manager.frames_dropped >= 100
        assert live._sent < len(live.world.log) or manager.frames_dropped > 0
        sent_before = live._sent
        # once the client catches up, the next frame carries what was held back
        stub.release.set()
        for _ in range(MAX_QUEUED_FRAMES + 50):
            await asyncio.sleep(0.001)
            if not conn.congested():
                break
        live._run_tick()
        assert live._sent == len(live.world.log) >= sent_before
        conn.writer.cancel()

    asyncio.run(scenario())


# ----------------------------------------------------------------------------- failures


def test_a_scenario_that_cannot_be_found_is_4404(live_client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.models import TrainingSession

    row = started(live_client)
    with Session(live_client.app.state.engine) as db:  # type: ignore[attr-defined]
        stored = db.get(TrainingSession, row["id"])
        assert stored is not None
        stored.scenario_id = "gone"
        db.commit()
    assert expect_close(live_client, row["id"]) == 4404


def test_a_world_that_cannot_be_built_closes_with_1011(
    live_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: LiveSession) -> None:
        raise RuntimeError("no sensors today")

    monkeypatch.setattr(LiveSession, "_make_world", broken)
    row = started(live_client)
    assert expect_close(live_client, row["id"]) == 1011
    assert manager_of(live_client).sessions == {}


def test_a_failure_inside_the_loop_stores_the_session_as_abandoned(
    live_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = [0]
    real = LiveSession._run_tick

    def flaky(self: LiveSession) -> None:
        calls[0] += 1
        if calls[0] == 5:
            raise RuntimeError("boom")
        real(self)

    monkeypatch.setattr(LiveSession, "_run_tick", flaky)
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        ended = sock.until("ended")
    assert ended["status"] == "abandoned" and ended["summary"]["ticks"] == 4
    assert live_client.get(f"/api/v1/sessions/{row['id']}").json()["status"] == "abandoned"
    assert manager_of(live_client).sessions == {}


def test_a_store_that_fails_is_reported_unverified(
    live_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: SessionManager, *args: Any) -> bool:
        raise RuntimeError("disk full")

    monkeypatch.setattr(SessionManager, "store", broken)
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.send({"t": "end"})
        assert sock.until("ended")["summary"]["verified"] is False


def test_a_vanished_row_is_reported_unverified(live_client: TestClient) -> None:
    row = started(live_client)
    manager = manager_of(live_client)
    assert manager.store("not-a-session", "ended", _record()) is False
    del row


def _record() -> Any:
    from sim import replay
    from tests.live_helpers import harrier_spec

    _, record = replay.run(harrier_spec(), 1, [], 5, picture=True, roe=True)
    return record


# ----------------------------------------------------------------------------- shutdown


def test_shutdown_stores_running_sessions_as_abandoned(live_client: TestClient) -> None:
    row = started(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(5)
        live_client.portal.call(manager_of(live_client).shutdown)  # type: ignore[union-attr]
        ended = sock.until("ended")
        assert ended["status"] == "abandoned" and ended["summary"]["verified"] is True
        with pytest.raises(WebSocketDisconnect):
            sock.recv()
    stored = live_client.get(f"/api/v1/sessions/{row['id']}").json()
    assert stored["status"] == "abandoned" and stored["ticks"] >= 5
    assert manager_of(live_client).sessions == {}


def test_two_sessions_run_side_by_side(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        first = create_session(client, login(client))
        second_csrf = login(client, "trainee2")
        second = create_session(client, second_csrf)
        with connect(client, second["id"]) as b:
            client.cookies.clear()
            login(client)
            with connect(client, first["id"]) as a:
                for sock in (a, b):
                    sock.until("frame")
                    sock.send({"t": "start"})
                ticks = [(a.frames(10)[-1]["tick"], b.frames(10)[-1]["tick"])]
                assert all(x >= 10 and y >= 10 for x, y in ticks)
                assert manager_of(client).stats()["running"] == 2


def test_the_join_frame_replays_the_events_so_far(live_client: TestClient) -> None:
    row = started(live_client)
    manager_of(live_client).speed = 40
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        track = ""
        while not track:
            track = next(
                (t["id"] for t in sock.until("frame")["tracks"] if t["status"] == "confirmed"), ""
            )
    manager_of(live_client).speed = 1
    with connect(live_client, row["id"]) as again:
        again.recv()
        join = again.recv()
    types = [e["type"] for e in join["events"]]
    assert types[0] == "session.start" and "track.confirm" in types
    assert [e["seq"] for e in join["events"]] == sorted(e["seq"] for e in join["events"])
    assert wire.trainee_events([]) == []
