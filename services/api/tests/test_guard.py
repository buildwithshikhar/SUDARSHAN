from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine
from app.guard import StartupError
from app.main import create_app
from app.models import Role
from app.users import upsert_demo_user
from tests.conftest import make_settings


def test_demo_mode_starts_with_no_secret(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, secret_key="")
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").status_code == 200


@pytest.mark.parametrize("secret", ["", "change-me", "short"])
def test_production_refuses_missing_default_or_short_secret(tmp_path: Path, secret: str) -> None:
    settings = make_settings(tmp_path, app_env="production", secret_key=secret)
    with pytest.raises(StartupError, match="SECRET_KEY"), TestClient(create_app(settings)):
        pass


def test_production_starts_with_strong_secret_and_no_demo_accounts(migrated: Settings) -> None:
    production = migrated.model_copy(update={"app_env": "production"})
    with TestClient(create_app(production)) as client:
        assert client.get("/api/v1/version").json()["env"] == "production"


def test_production_starts_before_migration(tmp_path: Path) -> None:
    # The users table does not exist yet; the guard must not crash on that.
    settings = make_settings(tmp_path, app_env="production")
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").status_code == 200


def test_production_refuses_when_demo_accounts_exist(migrated: Settings) -> None:
    with Session(make_engine(migrated.database_url)) as session:
        upsert_demo_user(session, "trainee@demo.invalid", Role.trainee, "demo-password-123")
    production = migrated.model_copy(update={"app_env": "production"})
    with pytest.raises(StartupError, match="demo accounts"), TestClient(create_app(production)):
        pass
