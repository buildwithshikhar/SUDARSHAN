from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alembic import command
from app.cli import _alembic_config
from app.config import Settings
from app.main import create_app

STRONG_KEY = "k" * 48


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "secret_key": STRONG_KEY,
        "git_sha": "abc1234",
        "build_time": "2026-01-01T00:00:00Z",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    command.upgrade(_alembic_config(settings), "head")
    return settings


@pytest.fixture
def client(migrated: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(migrated)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENV",
        "DATABASE_URL",
        "SECRET_KEY",
        "CORS_ORIGINS",
        "FIRST_ADMIN_EMAIL",
        "FIRST_ADMIN_PASSWORD",
        "BRAND_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
