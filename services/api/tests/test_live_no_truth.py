"""Nothing a trainee's socket carries may hold ground truth.

The whole scenario is played over a real WebSocket with every kind of operator action, then every
byte the server sent is scanned. The allow-list lives in `sim.audience`; this test is what makes it
a guarantee for the transport as well.
"""

import json
from pathlib import Path
from typing import Any

import msgpack  # type: ignore[import-untyped]
from fastapi.testclient import TestClient

from sim.audience import TRAINEE_EVENTS
from tests.live_helpers import harrier_spec
from tests.live_support import connect, create_session, fast, live_app, login

FORBIDDEN = ("contact-", "truth", "disposition", "true_class", "correct_flag", "ledger", "threat.")
FORBIDDEN_KEYS = frozenset({"target", "truth_id", "disposition", "true_class", "correct_flag"})


def walk_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key))
            found |= walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            found |= walk_keys(item)
    return found


def confirmed(frame: dict[str, Any]) -> list[str]:
    return [t["id"] for t in frame["tracks"] if t["status"] == "confirmed"]


def test_a_whole_session_over_the_socket_carries_no_ground_truth(tmp_path: Path) -> None:
    spec = harrier_spec()
    drone_ids = [t.id for t in spec.threats]
    with live_app(tmp_path, live_act_rate=10_000) as client:
        fast(client, 60)
        csrf = login(client)
        row = create_session(client, csrf)
        seq = 0
        worked: set[str] = set()
        acks: list[dict[str, Any]] = []
        with connect(client, row["id"]) as sock:
            welcome = sock.recv()
            assert sock.recv()["t"] == "frame"
            effector = welcome["rules"]["effector_classes"][0]["id"]
            sock.send({"t": "start"})

            def act(action: str, **payload: Any) -> None:
                nonlocal seq
                seq += 1
                sock.send({"t": "act", "seq": seq, "action": action, "payload": payload})

            while True:
                message = sock.recv()
                if message["t"] == "ack":
                    acks.append(message)
                if message["t"] == "ended":
                    break
                if message["t"] != "frame":
                    continue
                for track in confirmed(message):
                    if track in worked or len(worked) >= 4:
                        continue
                    worked.add(track)
                    act("designate", track=track)
                    act("classify", track=track, class_id="rotary-small")
                    act("assess", track=track, identity="hostile")
                    act("engage", track=track, effector_class=effector)
                    act("sensor-cue", sensor="eo-1", track=track)
                    act("track-relabel", track=track, label=f"W{len(worked)}")
                    act("report", track=track)
                    act("hold", track=track)
        assert worked, "the scenario produced no confirmed track to work on"
        assert all(a["ok"] for a in acks)

        decoded = [msgpack.unpackb(raw, raw=False) for raw in sock.raw]
        assert len(decoded) > 1000
        blob = b"".join(sock.raw)
        for needle in (*drone_ids, *FORBIDDEN):
            assert needle.encode() not in blob, f"{needle!r} is in what the server sent"
        text = json.dumps(decoded, sort_keys=True)
        for needle in (*drone_ids, *FORBIDDEN):
            assert needle not in text

        event_types: set[str] = set()
        for message in decoded:
            assert not walk_keys(message) & FORBIDDEN_KEYS, message["t"]
            if message["t"] == "frame":
                event_types |= {e["type"] for e in message["events"]}
        assert event_types <= TRAINEE_EVENTS
        # the working was seen: verdicts for the responses, and the accepted actions
        assert {"roe.verdict", "action.classify", "action.assess", "sensor.cue"} <= event_types
        assert {"track.init", "track.confirm", "session.start", "session.end"} <= event_types

        # the stored log, read as the trainee, passes the same scan
        log = client.get(f"/api/v1/sessions/{row['id']}/log").json()
        assert log["verified"] is True
        assert {e["type"] for e in log["events"]} <= TRAINEE_EVENTS
        for needle in (*drone_ids, *FORBIDDEN):
            assert needle not in json.dumps(log["events"])

        # the server's own record names the real drone behind each action; the client never did
        record_actions = json.loads(_record(client, row["id"]))["actions"]
        assert record_actions and all(
            "target" not in a["payload"] and a["actor"].startswith("trainee:")
            for a in record_actions
        )


def _record(client: TestClient, session_id: str) -> str:
    from sqlalchemy.orm import Session

    from app.models import TrainingSession

    with Session(client.app.state.engine) as db:  # type: ignore[attr-defined]
        row = db.get(TrainingSession, session_id)
        assert row is not None and row.record is not None
        return row.record


def test_a_real_action_comes_back_as_a_verdict_and_the_matching_event(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        fast(client, 20)
        csrf = login(client)
        row = create_session(client, csrf)
        with connect(client, row["id"]) as sock:
            welcome = sock.recv()
            sock.recv()
            effector = welcome["rules"]["effector_classes"][0]["id"]
            sock.send({"t": "start"})
            track = ""
            while not track:
                frame = sock.until("frame")
                track = next(iter(confirmed(frame)), "")

            def do(seq: int, action: str, **payload: Any) -> list[dict[str, Any]]:
                """Send one action and return the trainee events of the frames until it shows."""
                sock.send({"t": "act", "seq": seq, "action": action, "payload": payload})
                assert sock.until("ack")["ok"] is True
                seen: list[dict[str, Any]] = []
                for _ in range(400):
                    seen += sock.until("frame")["events"]
                    if any(e["type"] == "roe.verdict" for e in seen):
                        return seen
                raise AssertionError(f"no verdict for {action}")

            # a response before any assessment is blocked: a verdict, and no action event
            blocked = do(1, "engage", track=track, effector_class=effector)
            verdict = next(e for e in blocked if e["type"] == "roe.verdict")["payload"]
            assert verdict["track"] == track and verdict["action"] == "engage"
            assert verdict["permitted"] is False and verdict["code"] in ("conditions", "effector")
            assert verdict["pack_id"] == "training-baseline" and verdict["rule_title"]["en"]
            assert "action.engage" not in [e["type"] for e in blocked]

            # a classification is permitted: the verdict, then the matching action event
            events = do(2, "classify", track=track, class_id="rotary-small")
            types = [e["type"] for e in events]
            assert types.index("roe.verdict") < types.index("action.classify")
            permitted = next(e for e in events if e["type"] == "roe.verdict")["payload"]
            assert permitted["permitted"] is True and permitted["code"] == "permitted"
            accepted = next(e for e in events if e["type"] == "action.classify")
            assert accepted["payload"] == {"track": track, "class_id": "rotary-small"}
            assert accepted["actor"].startswith("trainee:")
