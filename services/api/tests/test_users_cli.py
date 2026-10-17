import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from alembic import command
from app.cli import _alembic_config, cli
from app.config import Settings
from app.db import make_engine
from app.models import Role, User
from app.security import verify_password
from app.users import UserError, create_admin, validate_email

runner = CliRunner()


def _env(settings: Settings, **extra: str) -> dict[str, str]:
    return {
        "DATABASE_URL": settings.database_url,
        "SECRET_KEY": settings.secret_key.get_secret_value(),
        **extra,
    }


def _users(settings: Settings) -> list[User]:
    with Session(make_engine(settings.database_url)) as session:
        return list(session.scalars(select(User)))


def test_migration_up_and_down(settings: Settings) -> None:
    config = _alembic_config(settings)
    command.upgrade(config, "head")
    assert _users(settings) == []
    command.downgrade(config, "base")
    with pytest.raises(Exception, match="users"):
        _users(settings)


def test_migrate_command(settings: Settings) -> None:
    result = runner.invoke(cli, ["migrate"], env=_env(settings))
    assert result.exit_code == 0
    assert _users(settings) == []


def test_create_admin_is_idempotent(migrated: Settings) -> None:
    env = _env(
        migrated, FIRST_ADMIN_EMAIL="Chief@Unit.example", FIRST_ADMIN_PASSWORD="a-long-password"
    )
    first = runner.invoke(cli, ["create-admin"], env=env)
    second = runner.invoke(cli, ["create-admin"], env=env)
    assert first.exit_code == 0 and "created: chief@unit.example" in first.output
    assert second.exit_code == 0 and "exists: chief@unit.example" in second.output
    users = _users(migrated)
    assert len(users) == 1
    assert users[0].role is Role.admin and users[0].is_demo is False
    assert verify_password(users[0].password_hash, "a-long-password")
    assert not verify_password(users[0].password_hash, "wrong")


def test_create_admin_rejects_short_password(migrated: Settings) -> None:
    result = runner.invoke(
        cli,
        ["create-admin"],
        env=_env(migrated, FIRST_ADMIN_EMAIL="a@b.example", FIRST_ADMIN_PASSWORD="short"),
    )
    assert result.exit_code == 1
    assert "at least 12" in result.output
    assert _users(migrated) == []


def test_create_admin_rejects_bad_email(migrated: Settings) -> None:
    with Session(make_engine(migrated.database_url)) as session, pytest.raises(UserError):
        create_admin(session, "not-an-email", "a-long-password")


def test_create_admin_refuses_to_promote_existing_user(migrated: Settings) -> None:
    with Session(make_engine(migrated.database_url)) as session:
        session.add(User(email="t@u.example", password_hash="x", role=Role.trainee))
        session.commit()
        with pytest.raises(UserError, match="not admin"):
            create_admin(session, "t@u.example", "a-long-password")


def test_create_admin_if_configured_skips_when_unset(migrated: Settings) -> None:
    result = runner.invoke(cli, ["create-admin", "--if-configured"], env=_env(migrated))
    assert result.exit_code == 0 and "skipping" in result.output
    assert _users(migrated) == []


def test_create_admin_prompts_when_unset(migrated: Settings) -> None:
    result = runner.invoke(
        cli,
        ["create-admin"],
        env=_env(migrated),
        input="ops@unit.example\na-long-password\na-long-password\n",
    )
    assert result.exit_code == 0 and "created: ops@unit.example" in result.output


def test_seed_demo_creates_three_flagged_accounts(migrated: Settings) -> None:
    first = runner.invoke(cli, ["seed-demo"], env=_env(migrated))
    second = runner.invoke(cli, ["seed-demo"], env=_env(migrated))
    assert first.exit_code == 0 and second.exit_code == 0
    users = _users(migrated)
    assert sorted(u.role.value for u in users) == ["admin", "instructor", "trainee"]
    assert all(u.is_demo and u.email.endswith("@demo.invalid") for u in users)
    assert first.output != second.output  # new passwords each run


def test_seed_demo_refuses_in_production(migrated: Settings) -> None:
    result = runner.invoke(cli, ["seed-demo"], env=_env(migrated, APP_ENV="production"))
    assert result.exit_code == 2
    assert "refuses" in result.output
    assert _users(migrated) == []


def test_validate_email_normalises() -> None:
    assert validate_email("  A@B.Example ") == "a@b.example"


def test_verify_password_rejects_garbage_hash() -> None:
    assert verify_password("not-a-hash", "x") is False


def test_check_passes_in_demo_and_fails_on_bad_production_secret(migrated: Settings) -> None:
    assert runner.invoke(cli, ["check"], env=_env(migrated)).exit_code == 0
    bad = runner.invoke(
        cli, ["check"], env={**_env(migrated, APP_ENV="production"), "SECRET_KEY": "x"}
    )
    assert bad.exit_code == 3
    assert "SECRET_KEY" in bad.output
    good = runner.invoke(cli, ["check"], env=_env(migrated, APP_ENV="production"))
    assert good.exit_code == 0 and "production" in good.output
