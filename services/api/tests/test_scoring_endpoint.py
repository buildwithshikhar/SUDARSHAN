"""The scored debrief of a session: stored when it ends, served to its owner, never early."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.cli import _alembic_config
from app.contracts import SessionScore
from app.models import TrainingSession
from tests.conftest import make_settings
from tests.live_support import create_session, login
from tests.test_live_rest import edit_row, play


def score_of(client: TestClient, session_id: str) -> dict[str, object]:
    response = client.get(f"/api/v1/sessions/{session_id}/score")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def stored_score(client: TestClient, session_id: str) -> str | None:
    from sqlalchemy.orm import Session

    with Session(client.app.state.engine) as db:  # type: ignore[attr-defined]
        row = db.get(TrainingSession, session_id)
        assert row is not None
        return row.score


def test_a_session_that_ends_is_scored_and_the_score_is_stored(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=2400)
    assert stored_score(live_client, row["id"]) is not None
    body = score_of(live_client, row["id"])
    score = SessionScore.model_validate(body)
    assert score.scenario.id == "harrier-morning-watch" and score.scenario.version == "1.0.0"
    assert (score.rule_pack.id, score.rule_pack.version) == ("training-baseline", "1.0.0")
    assert score.seed == row["seed"] and score.ticks >= 2400
    assert [t.threat_id for t in score.threats] == [
        "contact-bird-1",
        "contact-bird-2",
        "contact-bird-3",
        "contact-quad",
        "contact-civil",
    ]
    quad = next(t for t in score.threats if t.threat_id == "contact-quad")
    assert quad.presented and quad.score == 0.0  # reported by a sensor, never worked on
    assert quad.nodes[0].reason == "detect.missed"
    assert score.score is not None and score.score <= 0.0001
    assert len(score.event_head) == 64


def test_the_score_matches_the_head_of_the_verified_log(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=600)
    log = live_client.get(f"/api/v1/sessions/{row['id']}/log").json()
    assert score_of(live_client, row["id"])["event_head"] == log["head"]


def test_there_is_no_score_before_the_session_ends(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = create_session(live_client, csrf)
    response = live_client.get(f"/api/v1/sessions/{row['id']}/score")
    assert response.status_code == 409


def test_an_abandoned_session_has_no_score(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=300)
    edit_row(live_client, row["id"], lambda r: setattr(r, "status", "abandoned"))
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 409


def test_only_the_owner_can_read_a_score(live_client: TestClient) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=300)
    live_client.cookies.clear()
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 401
    login(live_client, "trainee2")
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 404
    login(live_client, "admin")
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 404
    login(live_client)
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 200


def test_an_ended_session_without_a_stored_score_is_scored_on_first_request(
    live_client: TestClient,
) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=1200)
    first = stored_score(live_client, row["id"])
    edit_row(live_client, row["id"], lambda r: setattr(r, "score", None))
    body = score_of(live_client, row["id"])
    again = stored_score(live_client, row["id"])
    assert again is not None
    assert json.loads(again) == body == json.loads(first or "")
    assert again == first  # scoring the same log again gives the same bytes


def test_a_scenario_that_is_no_longer_served_cannot_be_rescored(
    live_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=300)
    edit_row(live_client, row["id"], lambda r: setattr(r, "score", None))
    monkeypatch.setattr(live_client.app.state.live.catalog, "get", lambda *a, **k: None)  # type: ignore[attr-defined]
    assert live_client.get(f"/api/v1/sessions/{row['id']}/score").status_code == 409


def test_a_scoring_failure_never_loses_the_session_record(
    live_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("scoring is broken")

    monkeypatch.setattr("app.live.manager.score_session", broken)
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=300)  # play() asserts the ended message says verified
    assert stored_score(live_client, row["id"]) is None
    assert live_client.get(f"/api/v1/sessions/{row['id']}/log").json()["verified"] is True


def test_migration_0004_adds_and_removes_the_score_column(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    config = _alembic_config(settings)
    command.upgrade(config, "0003")
    engine = create_engine(settings.database_url)
    assert "score" not in {c["name"] for c in inspect(engine).get_columns("training_sessions")}
    command.upgrade(config, "head")
    columns = {c["name"]: c for c in inspect(engine).get_columns("training_sessions")}
    assert columns["score"]["nullable"]
    command.downgrade(config, "0003")
    assert "score" not in {c["name"] for c in inspect(engine).get_columns("training_sessions")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM training_sessions")).scalar_one() == 0
