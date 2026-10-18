"""Test support for the live session: users, sign-in, sessions and a decoded WebSocket."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import msgpack  # type: ignore[import-untyped]
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from alembic import command
from app.cli import _alembic_config
from app.config import Settings
from app.main import create_app
from app.models import Role
from tests.conftest import make_settings
from tests.helpers import PASSWORD, add_user

SCENARIO = "harrier-morning-watch"
ORIGIN = {"Origin": "http://testserver"}
EMAILS = {
    "trainee": "trainee@unit.example",
    "trainee2": "trainee2@unit.example",
    "instructor": "instructor@unit.example",
    "admin": "admin@unit.example",
}
ROLES = {
    "trainee": Role.trainee,
    "trainee2": Role.trainee,
    "instructor": Role.instructor,
    "admin": Role.admin,
}


def seed_users(settings: Settings) -> None:
    for name, email in EMAILS.items():
        add_user(settings, email, ROLES[name])


def login(client: TestClient, who: str = "trainee") -> dict[str, str]:
    """Sign in; returns the CSRF header for unsafe requests."""
    response = client.post("/api/v1/auth/login", json={"email": EMAILS[who], "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf"]}


def create_session(
    client: TestClient, csrf: dict[str, str], *, seed: int | None = None, scenario: str = SCENARIO
) -> dict[str, Any]:
    body: dict[str, Any] = {"scenario_id": scenario}
    if seed is not None:
        body["seed"] = seed
    response = client.post("/api/v1/sessions", json=body, headers=csrf)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


class Socket:
    """A WebSocket session that speaks MessagePack."""

    def __init__(self, ws: WebSocketTestSession) -> None:
        self.ws = ws
        #: Every raw frame received, for the tests that scan what the server sent.
        self.raw: list[bytes] = []

    def send(self, message: dict[str, Any]) -> None:
        self.ws.send_bytes(msgpack.packb(message, use_bin_type=True))

    def send_raw(self, data: bytes) -> None:
        self.ws.send_bytes(data)

    def recv(self) -> dict[str, Any]:
        data = self.ws.receive_bytes()
        self.raw.append(data)
        message: dict[str, Any] = msgpack.unpackb(data, raw=False)
        return message

    def until(self, kind: str, limit: int = 4000) -> dict[str, Any]:
        """Read messages until one of type `kind`; returns it."""
        for _ in range(limit):
            message = self.recv()
            if message["t"] == kind:
                return message
        raise AssertionError(f"no {kind!r} message within {limit} messages")

    def frames(self, count: int) -> list[dict[str, Any]]:
        return [self.until("frame") for _ in range(count)]


@contextmanager
def connect(
    client: TestClient, session_id: str, *, headers: dict[str, str] | None = None
) -> Iterator[Socket]:
    with client.websocket_connect(
        f"/api/v1/sessions/{session_id}/ws", headers=ORIGIN if headers is None else headers
    ) as ws:
        yield Socket(ws)


def live_app(tmp_path: Path, **overrides: object) -> TestClient:
    """A migrated app with the four test users; use it as a context manager."""
    settings = make_settings(tmp_path, **overrides)
    command.upgrade(_alembic_config(settings), "head")
    seed_users(settings)
    return TestClient(create_app(settings))


def expect_close(
    client: TestClient, session_id: str, *, headers: dict[str, str] | None = None
) -> int:
    """Connect and return the close code the server answered with."""
    try:
        with connect(client, session_id, headers=headers) as sock:
            sock.recv()
    except WebSocketDisconnect as closed:
        return closed.code
    raise AssertionError("the server did not close the socket")


def fast(client: TestClient, speed: float) -> None:
    """Run the live loop faster than 20 Hz; simulation time does not depend on wall time."""
    client.app.state.live.speed = speed  # type: ignore[attr-defined]
