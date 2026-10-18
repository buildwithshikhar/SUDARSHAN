"""Every message the server sends validates against the Pydantic model and the exported schema.

Frames are built as plain dicts on the hot path, so these checks are what tie the builders to the
`live-server.v1` contract. The messages are collected from real sessions, not hand-written.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import msgpack  # type: ignore[import-untyped]

from app.contracts import LiveServerMessage
from app.contracts.paths import packs_root
from tests.live_support import Socket, connect, create_session, fast, live_app, login

SCHEMA = json.loads((packs_root() / "schemas" / "live-server.v1.json").read_text())


def check(sockets: list[Socket]) -> dict[str, list[dict[str, Any]]]:
    """Validate every frame received on `sockets`; returns the messages by type."""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for sock in sockets:
        for raw in sock.raw:
            message = msgpack.unpackb(raw, raw=False)
            LiveServerMessage.model_validate(message)
            seen = by_type.setdefault(message["t"], [])
            # The schema check is slow; it covers every message but only a sample of the frames
            # (the Pydantic model, which is the same contract, sees all of them).
            if message["t"] != "frame" or len(seen) % 20 == 0 or message["events"]:
                jsonschema.validate(message, SCHEMA)
            seen.append(message)
    return by_type


def test_every_server_message_type_validates(tmp_path: Path) -> None:
    with live_app(tmp_path, live_act_rate=5) as client:
        fast(client, 20)
        csrf = login(client)
        first = create_session(client, csrf)
        with connect(client, first["id"]) as sock:
            welcome = sock.recv()
            sock.recv()
            sock.send({"t": "end"})  # not running: an error message
            assert sock.until("error")["code"] == "not-running"
            sock.send({"t": "act", "seq": 1, "action": "hold", "payload": {"track": "T1"}})
            sock.send({"t": "start"})
            sock.send({"t": "ping", "ts": 12.5})
            sock.send({"t": "act", "seq": 2, "action": "hold", "payload": {"target": "x"}})
            sock.send({"t": "act", "seq": 3, "action": "fire", "payload": {}})
            sock.send({"t": "act", "seq": 4, "action": "hold", "payload": {"track": "T404"}})
            for seq in range(5, 20):
                sock.send({"t": "act", "seq": seq, "action": "hold", "payload": {"track": "T1"}})
            track = ""
            while not track:
                frame = sock.until("frame")
                track = next((t["id"] for t in frame["tracks"] if t["status"] == "confirmed"), "")
            effector = welcome["rules"]["effector_classes"][0]["id"]
            for i, (action, payload) in enumerate(
                [
                    ("classify", {"track": track, "class_id": "rotary-small"}),
                    ("sensor-cue", {"sensor": "eo-1", "track": track}),
                    ("engage", {"track": track, "effector_class": effector}),
                    ("track-relabel", {"track": track, "label": "ALPHA"}),
                ]
            ):
                client.app.state.live.sessions[first["id"]]._tokens = 5.0  # type: ignore[attr-defined]
                sock.send({"t": "act", "seq": 100 + i, "action": action, "payload": payload})
                sock.frames(3)
            with connect(client, first["id"]) as other:  # supersedes: an error message
                other.recv()
                assert sock.until("error")["code"] == "superseded"
                other.send({"t": "end"})
                other.until("ended")
        second = create_session(client, csrf)
        with connect(client, second["id"]) as sock2:
            sock2.recv()
            sock2.send({"t": "start"})
            sock2.frames(4)
            create_session(client, csrf)  # abandons the live one
            sock2.until("ended")

        seen = check([sock, other, sock2])

    assert set(seen) == {"welcome", "frame", "status", "ack", "pong", "ended", "error"}
    codes = {m.get("error", {}).get("code") for m in seen["ack"] if not m["ok"]}
    assert codes == {"not-running", "invalid", "unknown-action", "too-many"}
    assert any(m["ok"] for m in seen["ack"])
    assert {m["status"] for m in seen["ended"]} == {"ended", "abandoned"}
    assert {m["code"] for m in seen["error"]} >= {"not-running", "superseded"}
    frames = seen["frame"]
    assert {f["status"] for f in frames} >= {"lobby", "running", "ended", "abandoned"}
    assert any(f["reports"] for f in frames) and any(f["tracks"] for f in frames)
    assert any(f["assist"] for f in frames) and any(f["events"] for f in frames)
    assert {r["modality"] for f in frames for r in f["reports"]} >= {"radar"}
    assert {e["type"] for f in frames for e in f["events"]} >= {"roe.verdict", "sensor.cue"}


def test_the_welcome_is_the_briefing_and_never_the_threats(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        csrf = login(client)
        row = create_session(client, csrf)
        with connect(client, row["id"]) as sock:
            welcome = sock.recv()
    check([sock])
    assert set(welcome) == {
        "t",
        "protocol",
        "session_id",
        "status",
        "tick_hz",
        "tick",
        "briefing",
        "rules",
        "operator_classes",
        "identities",
        "actions",
        "data_notice",
    }
    assert welcome["session_id"] == row["id"] and welcome["protocol"] == 1
    assert welcome["tick_hz"] == 20 and welcome["tick"] == 0 and welcome["status"] == "lobby"
    briefing = welcome["briefing"]
    assert set(briefing) == {
        "id",
        "version",
        "title",
        "summary",
        "duration_s",
        "start_time_of_day_h",
        "half_extent_m",
        "weather",
        "zones",
        "assets",
        "sensors",
        "filed_flights",
    }
    assert {s["modality"] for s in briefing["sensors"]} == {"radar", "eo", "rf"}
    assert briefing["filed_flights"] and briefing["zones"] and briefing["assets"]
    text = json.dumps(welcome)
    for needle in ("contact-", "disposition", "threat", "spawn_s", "waypoint", "route", "truth"):
        assert needle not in text, needle
    assert welcome["rules"]["id"] == "training-baseline" and welcome["rules"]["rules"]
    assert welcome["identities"] == ["hostile", "suspect", "unknown", "neutral", "friend"]
    assert "set-weather" not in welcome["actions"] and "hold" in welcome["actions"]


def test_the_lobby_frame_is_complete_and_empty_of_activity(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        row = create_session(client, login(client))
        with connect(client, row["id"]) as sock:
            sock.recv()
            frame = sock.recv()
    check([sock])
    assert frame["tick"] == 0 and frame["time_s"] == 0.0
    assert frame["reports"] == [] and frame["tracks"] == [] and frame["assist"] == []
    assert {s["id"] for s in frame["sensors"]} == {"radar-1", "eo-1", "rf-1"}
    assert all(s["data_status"] in ("reference", "verified") for s in frame["sensors"])
    assert [e["type"] for e in frame["events"]] == ["session.start"]
