"""The sessions REST API: scenarios, sessions, the verified log and the admin stats."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import TrainingSession
from tests.conftest import make_settings
from tests.live_support import SCENARIO, connect, create_session, fast, live_app, login


def edit_row(
    client: TestClient, session_id: str, change: Callable[[TrainingSession], None]
) -> None:
    with Session(client.app.state.engine) as db:  # type: ignore[attr-defined]
        row = db.get(TrainingSession, session_id)
        assert row is not None
        change(row)
        db.commit()


def edit_record(
    client: TestClient, session_id: str, change: Callable[[dict[str, Any]], None]
) -> None:
    def apply(row: TrainingSession) -> None:
        assert row.record is not None
        data = json.loads(row.record)
        change(data)
        row.record = json.dumps(data)

    edit_row(client, session_id, apply)


def play(
    client: TestClient, csrf: dict[str, str], *, ticks: int = 300, actions: bool = False
) -> dict[str, Any]:
    """Create a session, play `ticks` ticks at 100x (so 15 s of the scenario) and end it."""
    fast(client, 100)
    row = create_session(client, csrf)
    with connect(client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        if actions:
            sock.send({"t": "act", "seq": 1, "action": "hold", "payload": {"track": "T404"}})
        sock.frames(ticks)
        sock.send({"t": "end"})
        assert sock.until("ended")["summary"]["verified"] is True
    return row


# ----------------------------------------------------------------------------- scenarios


def test_scenarios_lists_the_playable_ones(live_client: TestClient) -> None:
    login(live_client)
    listed = live_client.get("/api/v1/scenarios").json()
    harrier = next(s for s in listed if s["id"] == SCENARIO)
    assert set(harrier) == {
        "id",
        "version",
        "title",
        "summary",
        "duration_s",
        "default_seed",
        "start_time_of_day_h",
        "weather_condition",
    }
    assert harrier["duration_s"] == 420 and harrier["title"]["en"] and harrier["title"]["hi"]
    assert [s["id"] for s in listed] == sorted(s["id"] for s in listed)
    assert "threats" not in json.dumps(listed)


def test_scenarios_need_a_player_role(live_client: TestClient) -> None:
    assert live_client.get("/api/v1/scenarios").status_code == 401
    login(live_client, "admin")
    assert live_client.get("/api/v1/scenarios").status_code == 403
    login(live_client, "instructor")
    assert live_client.get("/api/v1/scenarios").status_code == 200


def test_an_unloadable_scenario_is_not_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios = tmp_path / "packs" / "scenarios"
    scenarios.mkdir(parents=True)
    (scenarios / "broken.json").write_text("{not json")
    (scenarios / "wrong.json").write_text('{"contract": "rulepack.v1"}')
    from app.contracts.paths import packs_root
    from app.live.catalog import ScenarioCatalog

    real = packs_root() / "scenarios" / "harrier-morning-watch.v1.json"
    (scenarios / real.name).write_text(real.read_text())
    catalog = ScenarioCatalog(scenarios)
    assert list(catalog.entries()) == ["harrier-morning-watch"]
    assert catalog.get("harrier-morning-watch", "9.9.9") is None
    assert catalog.get("harrier-morning-watch", "1.0.0") is not None
    assert catalog.get("nothing") is None


# ----------------------------------------------------------------------------- create and read


def test_create_returns_a_lobby_session(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = create_session(live_client, csrf)
    assert row["status"] == "lobby" and row["ticks"] == 0 and row["seed"] == 260118
    assert row["scenario_version"] == "1.0.0" and row["started_at"] is None
    assert live_client.get(f"/api/v1/sessions/{row['id']}").json() == row
    chosen = create_session(live_client, csrf, seed=7)
    assert chosen["seed"] == 7


def test_create_needs_csrf_a_known_scenario_and_a_valid_seed(live_client: TestClient) -> None:
    csrf = login(live_client)
    body = {"scenario_id": SCENARIO}
    assert live_client.post("/api/v1/sessions", json=body).status_code == 403
    unknown = live_client.post("/api/v1/sessions", json={"scenario_id": "nope"}, headers=csrf)
    assert unknown.status_code == 404
    for seed in (-1, 2**63, "x"):
        bad = live_client.post("/api/v1/sessions", json={**body, "seed": seed}, headers=csrf)
        assert bad.status_code == 422, seed
    assert live_client.post("/api/v1/sessions", json={}, headers=csrf).status_code == 422


def test_admin_cannot_play_and_anonymous_is_refused(live_client: TestClient) -> None:
    body = {"scenario_id": SCENARIO}
    assert live_client.post("/api/v1/sessions", json=body).status_code == 401
    csrf = login(live_client, "admin")
    assert live_client.post("/api/v1/sessions", json=body, headers=csrf).status_code == 403
    assert live_client.get("/api/v1/sessions").status_code == 403


def test_an_instructor_may_play(live_client: TestClient) -> None:
    csrf = login(live_client, "instructor")
    assert create_session(live_client, csrf)["status"] == "lobby"


def test_a_new_session_abandons_the_earlier_unfinished_ones(live_client: TestClient) -> None:
    csrf = login(live_client)
    first = create_session(live_client, csrf)
    second = create_session(live_client, csrf)
    third = create_session(live_client, csrf)
    status = {r["id"]: r["status"] for r in live_client.get("/api/v1/sessions").json()}
    assert status == {first["id"]: "abandoned", second["id"]: "abandoned", third["id"]: "lobby"}
    ended = live_client.get(f"/api/v1/sessions/{first['id']}").json()
    assert ended["ended_at"] is not None


def test_sessions_are_listed_newest_first_and_only_for_their_owner(live_client: TestClient) -> None:
    csrf = login(live_client)
    older = create_session(live_client, csrf)
    newer = create_session(live_client, csrf)
    assert [r["id"] for r in live_client.get("/api/v1/sessions").json()] == [
        newer["id"],
        older["id"],
    ]
    live_client.cookies.clear()
    login(live_client, "trainee2")
    assert live_client.get("/api/v1/sessions").json() == []
    for url in ("", "/log"):
        assert live_client.get(f"/api/v1/sessions/{newer['id']}{url}").status_code == 404
    live_client.cookies.clear()
    login(live_client, "admin")
    assert live_client.get(f"/api/v1/sessions/{newer['id']}").status_code == 404
    assert live_client.get("/api/v1/sessions/not-a-session").status_code == 404


# ----------------------------------------------------------------------------- the log


def test_the_log_of_an_unfinished_session_is_a_conflict(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = create_session(live_client, csrf)
    assert live_client.get(f"/api/v1/sessions/{row['id']}/log").status_code == 409


def test_a_trainee_reads_the_projection_and_an_instructor_the_whole_chain(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        trainee_row = play(client, login(client))
        client.cookies.clear()
        instructor_row = play(client, login(client, "instructor"))

        as_instructor = client.get(f"/api/v1/sessions/{instructor_row['id']}/log").json()
        client.cookies.clear()
        login(client)
        as_trainee = client.get(f"/api/v1/sessions/{trainee_row['id']}/log").json()

    assert as_trainee["verified"] is True and as_trainee["first_bad_seq"] is None
    assert as_instructor["verified"] is True
    for log in (as_trainee, as_instructor):
        assert log["event_count"] >= 3 and len(log["head"]) == 64
        assert len(log["final_state_hash"]) == 64
    full = {e["type"] for e in as_instructor["events"]}
    seen = {e["type"] for e in as_trainee["events"]}
    assert len(as_instructor["events"]) == as_instructor["event_count"]
    assert "threat.spawn" in full
    assert not seen & {"threat.spawn", "threat.despawn", "assist.assess"}
    assert not any(t.startswith("ledger.") for t in seen)
    assert "session.start" in seen and "session.end" in seen
    assert "contact-" not in json.dumps(as_trainee["events"])
    assert "contact-" in json.dumps(as_instructor["events"])


def test_editing_one_stored_event_is_detected_at_that_event(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf)
    clean = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert clean["verified"] is True

    def tamper(data: dict[str, Any]) -> None:
        data["events"][2]["payload"]["tampered"] = True

    edit_record(live_client, row["id"], tamper)
    bad = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert bad["verified"] is False and bad["first_bad_seq"] == 2


def test_removing_an_event_or_changing_the_head_is_detected(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf)
    original = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()["event_count"]

    edit_record(live_client, row["id"], lambda d: d["events"].pop(1))
    removed = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert removed["verified"] is False and removed["first_bad_seq"] == 1

    second = play(live_client, csrf)
    edit_row(live_client, second["id"], lambda r: setattr(r, "event_head", "0" * 64))
    head = live_client.get(f"/api/v1/sessions/{second['id']}/log").json()
    assert head["verified"] is False and head["first_bad_seq"] == head["event_count"] - 1
    assert original >= 3


def test_a_corrupt_record_is_reported_not_raised(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf)
    edit_row(live_client, row["id"], lambda r: setattr(r, "record", "this is not json"))
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert log["verified"] is False and log["first_bad_seq"] == 0 and log["events"] == []


def test_a_trainee_log_skips_events_that_no_longer_parse(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf)

    def mangle(data: dict[str, Any]) -> None:
        data["events"][1] = {"seq": "one"}

    edit_record(live_client, row["id"], mangle)
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert log["verified"] is False and log["first_bad_seq"] == 1
    assert all(isinstance(e["seq"], int) for e in log["events"])


# ----------------------------------------------------------------------------- deep replay


def test_deep_replays_the_session_from_its_inputs(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, actions=True)
    shallow = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert "replay_matches" not in shallow
    deep = live_client.get(f"/api/v1/sessions/{row['id']}/log?deep=1").json()
    assert deep["verified"] is True and deep["replay_matches"] is True
    assert deep["replay_first_divergent_seq"] is None
    assert any(
        e["type"] == "action.rejected" for e in json.loads(_record(live_client, row))["events"]
    )


def _record(client: TestClient, row: dict[str, Any]) -> str:
    with Session(client.app.state.engine) as db:  # type: ignore[attr-defined]
        stored = db.get(TrainingSession, row["id"])
        assert stored is not None and stored.record is not None
        return stored.record


def test_deep_finds_a_record_whose_inputs_no_longer_give_its_events(
    live_client: TestClient,
) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, actions=True)

    def other_input(data: dict[str, Any]) -> None:
        data["actions"][0]["payload"] = {"track": "T405"}

    edit_record(live_client, row["id"], other_input)
    deep = live_client.get(f"/api/v1/sessions/{row['id']}/log?deep=1").json()
    assert deep["verified"] is True  # the events themselves are intact
    assert deep["replay_matches"] is False and isinstance(deep["replay_first_divergent_seq"], int)


def test_deep_says_so_when_it_cannot_replay(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf)
    edit_row(live_client, row["id"], lambda r: setattr(r, "scenario_id", "gone"))
    gone = live_client.get(f"/api/v1/sessions/{row['id']}/log?deep=1").json()
    assert gone["replay_matches"] is None

    other = play(live_client, csrf)
    edit_record(live_client, other["id"], lambda d: d.pop("final_state_hash"))
    broken = live_client.get(f"/api/v1/sessions/{other['id']}/log?deep=1").json()
    assert broken["replay_matches"] is False


# ----------------------------------------------------------------------------- stats and start-up


def test_stats_are_for_admins(live_client: TestClient) -> None:
    assert live_client.get("/api/v1/sessions/stats").status_code == 401
    csrf = login(live_client)
    play(live_client, csrf)
    assert live_client.get("/api/v1/sessions/stats").status_code == 403
    live_client.cookies.clear()
    login(live_client, "admin")
    stats = live_client.get("/api/v1/sessions/stats").json()
    assert stats["live_sessions"] == 0 and stats["completed_total"] == 1
    assert stats["started_total"] == 1 and stats["max_live_sessions"] == 32
    jitter = stats["tick_jitter_ms"]
    assert jitter["count"] >= 10 and 0 <= jitter["p50"] <= jitter["p95"] <= jitter["max"]
    assert stats["tick_cost_ms"]["count"] == jitter["count"]
    assert stats["lag_drops"] >= 0 and stats["frames_dropped"] >= 0


def test_a_session_left_running_by_an_earlier_process_is_abandoned_at_start(tmp_path: Path) -> None:
    with live_app(tmp_path) as client:
        row = create_session(client, login(client))
        edit_row(client, row["id"], lambda r: setattr(r, "status", "running"))
    with TestClient(create_app(make_settings(tmp_path))) as again:  # same database, new process
        login(again)
        assert again.get(f"/api/v1/sessions/{row['id']}").json()["status"] == "abandoned"


def test_a_running_session_shows_its_live_tick(live_client: TestClient) -> None:
    csrf = login(live_client)
    fast(live_client, 1)
    row = create_session(live_client, csrf)
    with connect(live_client, row["id"]) as sock:
        sock.until("frame")
        sock.send({"t": "start"})
        sock.frames(10)
        listed = live_client.get("/api/v1/sessions").json()[0]
        assert listed["status"] == "running" and listed["ticks"] >= 10
