"""The live WebSocket: who may connect, what it refuses, and the session lifecycle."""

import time
from pathlib import Path
from typing import Any

import msgpack  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.live_support import (
    connect,
    create_session,
    expect_close,
    live_app,
    login,
)


def wait_for(predicate: Any, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def start_session(client: TestClient) -> tuple[dict[str, str], dict[str, Any]]:
    csrf = login(client)
    return csrf, create_session(client, csrf)


# ----------------------------------------------------------------------------- refusals


def test_not_signed_in_is_4401(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    live_client.cookies.clear()
    assert expect_close(live_client, row["id"]) == 4401


def test_forged_cookie_is_4401(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    live_client.cookies.set("session", "forged-token")
    assert expect_close(live_client, row["id"]) == 4401


def test_unknown_session_is_4404(live_client: TestClient) -> None:
    login(live_client)
    assert expect_close(live_client, "00000000-0000-4000-8000-000000000000") == 4404


def test_another_users_session_is_4403(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    live_client.cookies.clear()
    login(live_client, "trainee2")
    assert expect_close(live_client, row["id"]) == 4403


def test_admin_cannot_join_is_4403(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    live_client.cookies.clear()
    login(live_client, "admin")
    assert expect_close(live_client, row["id"]) == 4403


def test_cross_site_origin_is_refused_at_the_handshake(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    evil = {"Origin": "https://evil.example"}
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        connect(live_client, row["id"], headers=evil) as sock,
    ):
        sock.recv()
    assert refused.value.code == 1008


def test_null_origin_is_refused(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with (
        pytest.raises(WebSocketDisconnect),
        connect(live_client, row["id"], headers={"Origin": "null"}) as sock,
    ):
        sock.recv()


def test_a_listed_origin_and_a_missing_origin_are_accepted(tmp_path: Path) -> None:
    with live_app(tmp_path, cors_origins="https://app.example, https://other.example") as client:
        _, row = start_session(client)
        for headers in (
            {"Origin": "https://app.example"},
            {"Origin": "https://other.example/"},
            {},
        ):
            with connect(client, row["id"], headers=headers) as sock:
                assert sock.recv()["t"] == "welcome"


def test_an_ended_session_is_4409(live_client: TestClient) -> None:
    csrf, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.send({"t": "end"})
        assert sock.until("ended")["status"] == "ended"
    assert expect_close(live_client, row["id"]) == 4409


def test_a_full_server_is_1013(tmp_path: Path) -> None:
    with live_app(tmp_path, max_live_sessions=1, session_grace_s=0.3) as client:
        _, first = start_session(client)
        with connect(client, first["id"]) as held:
            assert held.recv()["t"] == "welcome"
            second_csrf = login(client, "trainee2")
            second = create_session(client, second_csrf)
            assert expect_close(client, second["id"]) == 1013
        # the slot is free again once the first trainee has gone and the grace has run out
        wait_for(lambda: client.app.state.live.sessions == {})  # type: ignore[attr-defined]
        with connect(client, second["id"]) as sock:
            assert sock.recv()["t"] == "welcome"


# ----------------------------------------------------------------------------- malformed input


def refused_with(client: TestClient, send: Any) -> tuple[dict[str, Any], int]:
    """Connect, send via `send(sock)`, and return the server's error message and close code."""
    _, row = start_session(client)
    with connect(client, row["id"]) as sock:
        sock.until("frame")
        send(sock)
        error = sock.until("error")
        with pytest.raises(WebSocketDisconnect) as closed:
            sock.recv()
    return error, closed.value.code


def test_garbage_bytes_are_refused(live_client: TestClient) -> None:
    error, code = refused_with(live_client, lambda s: s.send_raw(b"\xc1\xc1\xc1not msgpack"))
    assert (error["code"], code) == ("invalid", 1007)


def test_a_message_that_is_not_a_map_is_refused(live_client: TestClient) -> None:
    error, code = refused_with(live_client, lambda s: s.send_raw(msgpack.packb([1, 2, 3])))
    assert (error["code"], code) == ("invalid", 1007)


def test_an_unknown_message_type_is_refused(live_client: TestClient) -> None:
    error, code = refused_with(live_client, lambda s: s.send({"t": "teleport"}))
    assert (error["code"], code) == ("invalid", 1007)


def test_extra_fields_on_a_message_are_refused(live_client: TestClient) -> None:
    error, code = refused_with(live_client, lambda s: s.send({"t": "start", "force": True}))
    assert (error["code"], code) == ("invalid", 1007)


def test_an_act_without_a_usable_seq_is_refused(live_client: TestClient) -> None:
    for seq in ("one", -1, True, 2**40):
        live_client.cookies.clear()
        error, code = refused_with(
            live_client, lambda s, seq=seq: s.send({"t": "act", "seq": seq, "action": "hold"})
        )
        assert (error["code"], code) == ("invalid", 1007)


def test_a_text_frame_is_refused(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.ws.send_text('{"t":"start"}')
        assert sock.until("error")["code"] == "invalid"
        with pytest.raises(WebSocketDisconnect) as closed:
            sock.recv()
    assert closed.value.code == 1003


def test_an_oversized_frame_is_4413(live_client: TestClient) -> None:
    error, code = refused_with(
        live_client,
        lambda s: s.send_raw(msgpack.packb({"t": "ping", "ts": 1.0, "pad": "x" * 20000})),
    )
    assert (error["code"], code) == ("too-large", 4413)


def test_a_frame_just_under_the_limit_is_handled(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "act", "seq": 1, "action": "hold", "payload": {"track": "x" * 64}})
        assert sock.until("ack")["seq"] == 1


# ----------------------------------------------------------------------------- the action whitelist


def act(sock: Any, seq: int, action: str, payload: Any) -> dict[str, Any]:
    sock.send({"t": "act", "seq": seq, "action": action, "payload": payload})
    ack: dict[str, Any] = sock.until("ack")
    assert ack["seq"] == seq
    return ack


def test_actions_before_the_start_are_not_running(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        ack = act(sock, 1, "hold", {"track": "T001"})
        assert ack["ok"] is False and ack["error"]["code"] == "not-running"


BAD_PAYLOADS = [
    ("classify", {"track": "T001", "class_id": "bird", "target": "contact-quad"}),  # no drone ids
    ("hold", {"track": "T001", "target": "contact-quad"}),
    ("hold", {"target": "contact-quad"}),
    ("hold", {}),
    ("hold", {"track": 5}),
    ("hold", {"track": ""}),
    ("hold", {"track": "T" * 65}),
    ("hold", {"track": ["T001"]}),
    ("hold", {"track": None}),
    ("classify", {"track": "T001"}),
    ("assess", {"track": "T001", "identity": 3}),
    ("engage", {"track": "T001", "effector_class": {"id": "ec-a"}}),
    ("engage", {"track": "T001", "effector_class": "ec-a", "extra": 1}),
    ("track-relabel", {"track": "T001", "label": "A", "exchange": "yes"}),
    ("track-merge", {"tracks": "T001"}),
    ("track-merge", {"tracks": ["T001"]}),
    ("track-merge", {"tracks": ["T001", "T002", "T003"]}),
    ("track-merge", {"tracks": ["T001", 2]}),
    ("sensor-cue", {"sensor": "eo-1", "track": "T001", "narrow": 1}),
    ("sensor-cue", {"sensor": "eo-1"}),
    ("designate", [1, 2]),
    ("designate", "T001"),
    ("report", {"track": "T001", "count": "two"}),
    ("report", {"track": "T001", "confidence": True}),
    ("report", {"track": "T001", "speed": 3}),
    ("hold", {"track": "T001", "count": 2}),
]


@pytest.mark.parametrize(("action", "payload"), BAD_PAYLOADS)
def test_a_malformed_payload_is_acked_invalid_and_never_queued(
    live_client: TestClient, action: str, payload: Any
) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        ack = act(sock, 7, action, payload)
        assert ack["ok"] is False and ack["error"]["code"] == "invalid"
        sock.send({"t": "end"})
        assert sock.until("ended")["summary"]["verified"] is True
    record = stored_record(live_client, row["id"])
    assert record["actions"] == []


def test_unknown_actions_are_acked_unknown_action(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        for seq, action in enumerate(["set-weather", "fire", "", "HOLD", 5, None]):
            sock.send({"t": "act", "seq": seq, "action": action, "payload": {}})
            ack = sock.until("ack")
            assert ack["ok"] is False and ack["error"]["code"] == "unknown-action", action
        sock.send({"t": "end"})
        sock.until("ended")
    assert stored_record(live_client, row["id"])["actions"] == []


def test_a_mistyped_act_envelope_is_acked_invalid(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.send({"t": "act", "seq": 3, "action": "hold", "payload": {"track": "T1"}, "tick": 0})
        ack = sock.until("ack")
        assert ack["error"]["code"] == "invalid"
        sock.send({"t": "act", "seq": 4, "action": "hold", "payload": {"track": b"bytes"}})
        assert sock.until("ack")["error"]["code"] == "invalid"


def test_a_good_action_is_stamped_by_the_server(live_client: TestClient) -> None:
    csrf, row = start_session(live_client)
    me = live_client.get("/api/v1/auth/me").json()["user"]["id"]
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        ack = act(sock, 9, "hold", {"track": "T404"})  # no such track: the world will reject it
        assert ack["ok"] is True and isinstance(ack["tick"], int)
        sock.frames(3)
        sock.send({"t": "end"})
        sock.until("ended")
    (action,) = stored_record(live_client, row["id"])["actions"]
    assert action["actor"] == f"trainee:{me}"
    assert action["action"] == "hold" and action["payload"] == {"track": "T404"}
    assert action["tick"] >= ack["tick"]


def test_the_act_rate_is_limited(tmp_path: Path) -> None:
    with live_app(tmp_path, live_act_rate=5) as client:
        _, row = start_session(client)
        with connect(client, row["id"]) as sock:
            sock.until("frame")
            for seq in range(30):
                sock.send({"t": "act", "seq": seq, "action": "hold", "payload": {"track": "T1"}})
            codes = [sock.until("ack").get("error", {}).get("code") for _ in range(30)]
        assert codes[0] == "not-running" and codes.count("too-many") >= 20


# ----------------------------------------------------------------------------- lifecycle


def test_ping_is_echoed_with_the_tick(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "ping", "ts": 1234.5})
        assert sock.until("pong") == {"t": "pong", "ts": 1234.5, "tick": 0}


def test_start_changes_status_once_and_ticking_follows(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        welcome = sock.recv()
        first = sock.recv()
        assert (welcome["status"], first["status"], first["tick"]) == ("lobby", "lobby", 0)
        sock.send({"t": "start"})
        assert sock.until("status") == {"t": "status", "status": "running", "tick": 0}
        ticks = [f["tick"] for f in sock.frames(5)]
        assert ticks == sorted(ticks) and len(set(ticks)) == 5
        sock.send({"t": "start"})  # idempotent
        assert sock.until("status")["status"] == "running"
    got = live_client.get(f"/api/v1/sessions/{row['id']}").json()
    assert got["status"] == "running" and got["started_at"] is not None


def test_end_before_start_is_an_error_message_not_a_close(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "end"})
        assert sock.until("error")["code"] == "not-running"
        sock.send({"t": "ping", "ts": 1.0})
        assert sock.until("pong")


def test_end_stores_the_session_and_reports_it_verified(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(10)
        sock.send({"t": "end"})
        ended = sock.until("ended")
        with pytest.raises(WebSocketDisconnect) as closed:
            sock.recv()
    assert closed.value.code == 1000
    summary = ended["summary"]
    assert summary["verified"] is True and summary["ticks"] >= 10
    assert summary["duration_s"] == summary["ticks"] / 20
    stored = live_client.get(f"/api/v1/sessions/{row['id']}").json()
    assert stored["status"] == "ended" and stored["ticks"] == summary["ticks"]
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert log["head"] == summary["head"] and log["event_count"] == summary["event_count"]


def test_supersede_closes_the_older_connection_with_4408(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as older:
        older.until("frame")
        with connect(live_client, row["id"]) as newer:
            assert newer.recv()["t"] == "welcome"
            assert older.until("error")["code"] == "superseded"
            with pytest.raises(WebSocketDisconnect) as closed:
                older.recv()
            assert closed.value.code == 4408
            newer.send({"t": "ping", "ts": 2.0})
            assert newer.until("pong")["ts"] == 2.0
        # the older socket's departure must not have paused or ended the newer one's session
    assert live_client.get(f"/api/v1/sessions/{row['id']}").json()["status"] in (
        "lobby",
        "abandoned",
    )


def test_leave_pauses_and_a_rejoin_resumes_the_same_tick(tmp_path: Path) -> None:
    with live_app(tmp_path, session_grace_s=30) as client:
        _, row = start_session(client)
        with connect(client, row["id"]) as sock:
            sock.until("frame")
            sock.send({"t": "start"})
            sock.frames(5)
            sock.send({"t": "leave"})
            with pytest.raises(WebSocketDisconnect) as closed:
                while True:
                    sock.recv()
            assert closed.value.code == 1000
        live = client.app.state.live.sessions[row["id"]]  # type: ignore[attr-defined]
        paused_at = live.world.tick
        time.sleep(0.4)
        assert live.world.tick == paused_at  # nothing ticks without a client
        with connect(client, row["id"]) as sock:
            welcome = sock.recv()
            assert welcome["status"] == "running" and welcome["tick"] == paused_at
            join = sock.recv()
            assert join["tick"] == paused_at
            assert [e["type"] for e in join["events"]][0] == "session.start"
            assert sock.until("frame")["tick"] == paused_at + 1
            sock.send({"t": "end"})
            assert sock.until("ended")["summary"]["verified"] is True


def test_a_dropped_connection_pauses_then_abandons_after_the_grace(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(5)
    sessions = live_client.app.state.live.sessions  # type: ignore[attr-defined]
    wait_for(lambda: row["id"] not in sessions)  # grace is 0.4 s here
    stored = live_client.get(f"/api/v1/sessions/{row['id']}").json()
    assert stored["status"] == "abandoned" and stored["ticks"] >= 5
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert log["verified"] is True and log["events"][-1]["type"] == "session.end"
    assert expect_close(live_client, row["id"]) == 4409
    assert live_client.app.state.live.stats()["abandoned_total"] == 1  # type: ignore[attr-defined]


def test_a_lobby_session_nobody_returns_to_is_abandoned(live_client: TestClient) -> None:
    _, row = start_session(live_client)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
    wait_for(
        lambda: live_client.get(f"/api/v1/sessions/{row['id']}").json()["status"] == "abandoned"
    )


def test_a_new_session_abandons_the_live_one(live_client: TestClient) -> None:
    csrf, old = start_session(live_client)
    with connect(live_client, old["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(3)
        new = create_session(live_client, csrf)
        ended = sock.until("ended")
        assert ended["status"] == "abandoned" and ended["summary"]["verified"] is True
    assert live_client.get(f"/api/v1/sessions/{old['id']}").json()["status"] == "abandoned"
    assert live_client.get(f"/api/v1/sessions/{new['id']}").json()["status"] == "lobby"


def test_a_scenario_that_ends_by_itself_is_stored(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        client.app.state.live.speed = 400.0  # type: ignore[attr-defined]
        _, row = start_session(client)
        with connect(client, row["id"]) as sock:
            sock.until("frame")
            sock.send({"t": "start"})
            ended = sock.until("ended", limit=20000)
        assert ended["summary"]["ticks"] == 8400 and ended["summary"]["verified"] is True
        assert client.get(f"/api/v1/sessions/{row['id']}").json()["status"] == "ended"


def stored_record(client: TestClient, session_id: str) -> dict[str, Any]:
    import json

    from sqlalchemy.orm import Session

    from app.models import TrainingSession

    with Session(client.app.state.engine) as db:  # type: ignore[attr-defined]
        row = db.get(TrainingSession, session_id)
        assert row is not None and row.record is not None
        record: dict[str, Any] = json.loads(row.record)
        return record


def test_the_radar_only_kestrel_scenario_also_plays_to_the_end(live_client: TestClient) -> None:
    """A scenario without an EO sensor is still playable; the briefing simply lists no camera."""
    from tests.live_support import fast

    csrf = login(live_client)
    row = create_session(live_client, csrf, scenario="kestrel-dawn-approach")
    fast(live_client, 400.0)
    with connect(live_client, row["id"]) as sock:
        welcome = sock.until("welcome")
        assert [s["modality"] for s in welcome["briefing"]["sensors"]] == ["radar"]
        sock.send({"t": "start"})
        sock.until("ended", limit=20000)
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert log["verified"] is True
    assert log["events"][-1]["type"] == "session.end"
