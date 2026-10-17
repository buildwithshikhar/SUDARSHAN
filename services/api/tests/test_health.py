from pathlib import Path

from fastapi.testclient import TestClient

from app.brand import load_brand
from app.main import create_app, get_app
from tests.conftest import make_settings

UNREACHABLE_DB = "postgresql+psycopg://u:p@127.0.0.1:1/none"


def test_healthz_does_not_touch_the_database(tmp_path: Path) -> None:
    # No migration and an unusable database path: liveness must still be ok.
    app = create_app(make_settings(tmp_path, database_url=UNREACHABLE_DB))
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_ready_with_database(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_unavailable_without_database(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, database_url=UNREACHABLE_DB))
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_version_reads_brand_and_build_info(client: TestClient) -> None:
    body = client.get("/api/v1/version").json()
    assert body["productName"] == load_brand().productName
    assert body["descriptor"]
    assert body["gitSha"] == "abc1234"
    assert body["buildTime"] == "2026-01-01T00:00:00Z"
    assert body["env"] == "demo"
    assert body["version"]


def test_cors_headers_only_for_configured_origins(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, cors_origins="https://front.example"))
    with TestClient(app) as client:
        allowed = client.get("/healthz", headers={"Origin": "https://front.example"})
        denied = client.get("/healthz", headers={"Origin": "https://other.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://front.example"
    assert "access-control-allow-origin" not in denied.headers


def test_get_app_factory_builds_an_app(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    assert get_app().title
