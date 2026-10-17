from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth import Principal, require_roles
from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.models import Role, SessionRecord
from app.ratelimit import LoginRateLimiter
from tests.conftest import make_settings
from tests.helpers import PASSWORD, add_user

LOGIN = "/api/v1/auth/login"
EMAILS = {
    Role.trainee: "trainee@unit.example",
    Role.instructor: "instructor@unit.example",
    Role.admin: "admin@unit.example",
}


def _login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, object]:
    response = client.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


@pytest.fixture
def seeded(migrated: Settings) -> Settings:
    for role, email in EMAILS.items():
        add_user(migrated, email, role)
    return migrated


@pytest.fixture
def app_client(seeded: Settings) -> TestClient:
    return TestClient(create_app(seeded))


def test_login_sets_httponly_lax_cookie_and_returns_csrf(app_client: TestClient) -> None:
    response = app_client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie
    body = response.json()
    assert body["user"]["role"] == "admin" and body["csrf"] and "password" not in str(body)
    assert app_client.get("/api/v1/auth/me").json()["user"]["email"] == EMAILS[Role.admin]


def test_email_is_case_insensitive(app_client: TestClient) -> None:
    _login(app_client, "  ADMIN@Unit.Example ")


def test_wrong_password_and_unknown_user_give_the_same_error(app_client: TestClient) -> None:
    wrong = app_client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": "nope"})
    unknown = app_client.post(LOGIN, json={"email": "ghost@unit.example", "password": "nope"})
    junk = app_client.post(LOGIN, json={"email": "not an email", "password": "nope"})
    assert wrong.status_code == unknown.status_code == junk.status_code == 401
    assert wrong.json() == unknown.json() == junk.json()


def test_me_requires_a_session(app_client: TestClient) -> None:
    assert app_client.get("/api/v1/auth/me").status_code == 401
    app_client.cookies.set("session", "forged-token")
    assert app_client.get("/api/v1/auth/me").status_code == 401


def test_rate_limit_blocks_then_recovers(seeded: Settings) -> None:
    clock = [0.0]
    app = create_app(seeded)
    app.state.rate_limiter = LoginRateLimiter(5, 900, lambda: clock[0])
    client = TestClient(app)
    for _ in range(5):
        assert (
            client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": "x"}).status_code
            == 401
        )
    blocked = client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": PASSWORD})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    clock[0] += 901
    assert (
        client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": PASSWORD}).status_code
        == 200
    )


def test_successful_login_resets_the_counter(seeded: Settings) -> None:
    app = create_app(seeded)
    client = TestClient(app)
    for _ in range(4):
        client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": "x"})
    _login(client, EMAILS[Role.admin])
    for _ in range(4):
        assert (
            client.post(LOGIN, json={"email": EMAILS[Role.admin], "password": "x"}).status_code
            == 401
        )


def test_logout_needs_csrf_and_ends_the_session(app_client: TestClient) -> None:
    csrf = str(_login(app_client, EMAILS[Role.trainee])["csrf"])
    assert app_client.post("/api/v1/auth/logout").status_code == 403
    assert (
        app_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    )
    assert app_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert app_client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected_and_removed(seeded: Settings) -> None:
    client = TestClient(create_app(seeded))
    _login(client, EMAILS[Role.trainee])
    engine = make_engine(seeded.database_url)
    with Session(engine) as session:
        session.execute(
            update(SessionRecord).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        session.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as session:
        assert session.query(SessionRecord).count() == 0


def test_session_token_is_not_stored_in_clear(seeded: Settings) -> None:
    client = TestClient(create_app(seeded))
    _login(client, EMAILS[Role.admin])
    token = client.cookies.get("session")
    with Session(make_engine(seeded.database_url)) as session:
        ids = [r.id for r in session.query(SessionRecord)]
    assert token and token not in ids and len(ids[0]) == 64


def test_preferences_need_csrf_validate_and_persist(seeded: Settings) -> None:
    client = TestClient(create_app(seeded))
    csrf = str(_login(client, EMAILS[Role.trainee])["csrf"])
    url = "/api/v1/auth/me/preferences"
    assert client.patch(url, json={"theme": "light"}).status_code == 403
    assert (
        client.patch(url, json={"theme": "pink"}, headers={"X-CSRF-Token": csrf}).status_code == 422
    )
    assert (
        client.patch(url, json={"language": "xx"}, headers={"X-CSRF-Token": csrf}).status_code
        == 422
    )
    ok = client.patch(
        url, json={"language": "hi", "theme": "light"}, headers={"X-CSRF-Token": csrf}
    )
    assert ok.status_code == 200 and ok.json()["language"] == "hi"
    other = TestClient(create_app(seeded))
    user = _login(other, EMAILS[Role.trainee])["user"]
    assert isinstance(user, dict) and user["language"] == "hi" and user["theme"] == "light"


def test_users_route_is_admin_only(seeded: Settings) -> None:
    anonymous = TestClient(create_app(seeded))
    assert anonymous.get("/api/v1/users").status_code == 401
    for role, expected in ((Role.trainee, 403), (Role.instructor, 403), (Role.admin, 200)):
        client = TestClient(create_app(seeded))
        _login(client, EMAILS[role])
        assert client.get("/api/v1/users").status_code == expected, role
    rows = client.get("/api/v1/users").json()
    assert {r["email"] for r in rows} == set(EMAILS.values())
    assert all("password" not in r and "hash" not in str(r).lower() for r in rows)


def test_role_guard_matrix(seeded: Settings) -> None:
    probe = APIRouter()

    def guarded(*roles: Role) -> object:
        def route(_: Principal = Depends(require_roles(*roles))) -> dict[str, str]:
            return {"ok": "yes"}

        return route

    probe.add_api_route("/probe/trainee", guarded(Role.trainee), methods=["GET"])  # type: ignore[arg-type]
    probe.add_api_route("/probe/instructor", guarded(Role.instructor, Role.admin), methods=["GET"])  # type: ignore[arg-type]
    probe.add_api_route("/probe/admin", guarded(Role.admin), methods=["GET"])  # type: ignore[arg-type]
    allowed = {
        Role.trainee: {"trainee"},
        Role.instructor: {"instructor"},
        Role.admin: {"instructor", "admin"},
    }
    for role, email in EMAILS.items():
        app = create_app(seeded)
        app.include_router(probe)
        client = TestClient(app)
        _login(client, email)
        for name in ("trainee", "instructor", "admin"):
            status = client.get(f"/probe/{name}").status_code
            assert status == (200 if name in allowed[role] else 403), (role, name)


def test_production_refuses_demo_accounts_at_login_and_sets_secure_cookie(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, app_env="production")
    from alembic import command
    from app.cli import _alembic_config

    command.upgrade(_alembic_config(settings), "head")
    add_user(settings, "real@unit.example", Role.admin)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        # a demo account appearing after start-up still cannot sign in
        add_user(settings, "demo@demo.invalid", Role.trainee, is_demo=True)
        denied = client.post(LOGIN, json={"email": "demo@demo.invalid", "password": PASSWORD})
        assert denied.status_code == 401
        ok = client.post(LOGIN, json={"email": "real@unit.example", "password": PASSWORD})
        assert ok.status_code == 200 and "secure" in ok.headers["set-cookie"].lower()


def test_upload_directory_is_created_at_start(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "uploads"
    with TestClient(create_app(make_settings(tmp_path, upload_dir=str(target)))):
        assert target.is_dir()


def test_cors_allows_credentials_for_configured_origin(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, cors_origins="https://front.example"))
    with TestClient(app) as client:
        preflight = client.options(
            LOGIN,
            headers={
                "Origin": "https://front.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-csrf-token,content-type",
            },
        )
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert "x-csrf-token" in preflight.headers["access-control-allow-headers"].lower()
