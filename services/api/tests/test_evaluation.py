"""Evaluation mode: one-click seats for the public evaluation link, off unless asked for."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.auth import Principal, forbid_in_evaluation
from app.cli import cli
from app.config import Settings
from app.db import make_engine
from app.guard import StartupError
from app.main import create_app
from app.models import Role, ScenarioRecord, SessionRecord, TrainingSession, User
from tests.conftest import make_settings
from tests.helpers import add_user

ENTRY = "/api/v1/auth/evaluation-login"
SEATS = {
    "trainee": "trainee",
    "commander": "trainee",
    "instructor": "instructor",
    "admin": "admin",
}


def _reset(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("EVALUATION_MODE", "true")
    result = CliRunner().invoke(cli, ["eval-reset"])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.fixture
def evaluation(migrated: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    _reset(migrated, monkeypatch)
    return migrated.model_copy(update={"evaluation_mode": True})


def test_the_flag_is_off_in_the_default_configuration(settings: Settings) -> None:
    assert Settings().evaluation_mode is False
    assert settings.evaluation_mode is False
    production = make_settings(Path("."), app_env="production")
    assert production.evaluation_mode is False


def test_the_entry_does_not_exist_unless_the_flag_is_on(client: TestClient) -> None:
    assert client.post(ENTRY, json={"seat": "trainee"}).status_code == 404


def test_production_without_the_flag_still_refuses_demo_accounts_and_demo_sign_in(
    migrated: Settings,
) -> None:
    add_user(migrated, "trainee@demo.invalid", Role.trainee, is_demo=True)
    production = migrated.model_copy(update={"app_env": "production"})
    with pytest.raises(StartupError, match="demo accounts"), TestClient(create_app(production)):
        pass


def test_each_seat_signs_in_without_a_password_and_the_cookie_works(evaluation: Settings) -> None:
    for seat, role in SEATS.items():
        with TestClient(create_app(evaluation)) as client:
            response = client.post(ENTRY, json={"seat": seat})
            assert response.status_code == 200, response.text
            assert response.json()["user"]["role"] == role
            assert client.get("/api/v1/auth/me").json()["user"]["role"] == role


def test_in_production_the_seats_start_and_enter_but_a_password_never_works(
    evaluation: Settings,
) -> None:
    production = evaluation.model_copy(update={"app_env": "production"})
    with TestClient(create_app(production)) as client:
        assert client.post(ENTRY, json={"seat": "admin"}).status_code == 200
        client.cookies.clear()
        login = client.post(
            "/api/v1/auth/login", json={"email": "admin@demo.invalid", "password": "x" * 20}
        )
        assert login.status_code == 401
        cookie = client.post(ENTRY, json={"seat": "admin"}).headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie


def test_the_session_is_short_and_the_entry_is_rate_limited(evaluation: Settings) -> None:
    limited = evaluation.model_copy(update={"evaluation_rate_max": 3})
    with TestClient(create_app(limited)) as client:
        first = client.post(ENTRY, json={"seat": "trainee"})
        hours = (
            datetime.fromisoformat(first.json()["expiresAt"]) - datetime.now(UTC)
        ).total_seconds() / 3600
        assert 2.5 < hours <= limited.evaluation_session_ttl_hours
        assert "Max-Age=10800" in first.headers["set-cookie"]
        assert client.post(ENTRY, json={"seat": "trainee"}).status_code == 200
        assert client.post(ENTRY, json={"seat": "trainee"}).status_code == 200
        blocked = client.post(ENTRY, json={"seat": "trainee"})
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0


def test_an_unknown_seat_is_refused(evaluation: Settings) -> None:
    with TestClient(create_app(evaluation)) as client:
        assert client.post(ENTRY, json={"seat": "root"}).status_code == 422


def test_unseeded_seats_say_so(migrated: Settings) -> None:
    on = migrated.model_copy(update={"evaluation_mode": True})
    with TestClient(create_app(on)) as client:
        response = client.post(ENTRY, json={"seat": "trainee"})
        assert response.status_code == 503
        assert "reset" in response.json()["detail"]


def test_an_ordinary_account_cannot_be_entered_this_way(evaluation: Settings) -> None:
    with Session(make_engine(evaluation.database_url)) as db:
        user = db.scalar(select(User).where(User.email == "admin@demo.invalid"))
        assert user is not None
        user.is_demo = False
        db.commit()
    with TestClient(create_app(evaluation)) as client:
        assert client.post(ENTRY, json={"seat": "admin"}).status_code == 503


def test_evaluation_seats_are_refused_on_guarded_routes_and_real_admins_are_not(
    evaluation: Settings,
) -> None:
    add_user(evaluation, "real.admin@unit.example", Role.admin)
    app = create_app(evaluation)
    guarded = APIRouter()

    @guarded.post("/_guarded")
    def route(_: Principal = Depends(forbid_in_evaluation)) -> dict[str, bool]:
        return {"ok": True}

    app.include_router(guarded)
    with TestClient(app) as client:
        session = client.post(ENTRY, json={"seat": "admin"}).json()
        denied = client.post("/_guarded", headers={"X-CSRF-Token": session["csrf"]})
        assert denied.status_code == 403
        assert "evaluation" in denied.json()["detail"]
    with TestClient(app) as client:
        from tests.helpers import PASSWORD

        body = {"email": "real.admin@unit.example", "password": PASSWORD}
        real = client.post("/api/v1/auth/login", json=body).json()
        assert client.post("/_guarded", headers={"X-CSRF-Token": real["csrf"]}).status_code == 200


def test_reset_restores_the_seeded_state_and_leaves_other_accounts_alone(
    evaluation: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_user(evaluation, "someone@unit.example", Role.trainee)
    with TestClient(create_app(evaluation)) as client:
        session = client.post(ENTRY, json={"seat": "trainee"}).json()
        client.patch(
            "/api/v1/auth/me/preferences",
            json={"language": "hi", "theme": "light"},
            headers={"X-CSRF-Token": session["csrf"]},
        )
    engine = make_engine(evaluation.database_url)
    with Session(engine) as db:
        demo_id = db.scalar(select(User.id).where(User.email == "trainee@demo.invalid"))
        other_id = db.scalar(select(User.id).where(User.email == "someone@unit.example"))
        assert demo_id is not None and other_id is not None
        for owner in (demo_id, other_id):
            db.add(TrainingSession(user_id=owner, scenario_id="s", scenario_version="1", seed=1))
            db.add(
                ScenarioRecord(
                    id=f"mine-{owner}",
                    version="1",
                    owner_id=owner,
                    origin="authored",
                    spec="{}",
                    spec_sha256="0" * 64,
                )
            )
        db.commit()
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == 1
    out = _reset(evaluation, monkeypatch)
    assert "removed 1 sign-in sessions" in out
    with Session(engine) as db:
        demo = db.scalar(select(User).where(User.email == "trainee@demo.invalid"))
        assert demo is not None
        assert (demo.language, demo.theme) == ("en", "dark")
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == 0
        owners = set(db.scalars(select(TrainingSession.user_id)))
        assert owners == {other_id}
        assert set(db.scalars(select(ScenarioRecord.owner_id))) == {other_id}
        assert db.scalar(select(User.id).where(User.email == "someone@unit.example")) == other_id


def test_reset_refuses_without_the_flag(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated.database_url)
    monkeypatch.delenv("EVALUATION_MODE", raising=False)
    result = CliRunner().invoke(cli, ["eval-reset"])
    assert result.exit_code == 2
    assert "EVALUATION_MODE" in result.output


def test_no_password_is_printed_or_kept_by_reset(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _reset(migrated, monkeypatch)
    with Session(make_engine(migrated.database_url)) as db:
        hashes = list(db.scalars(select(User.password_hash).where(User.is_demo.is_(True))))
    assert len(hashes) == 3
    assert all(h not in out for h in hashes)
    assert "password" not in out.lower()
