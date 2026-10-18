"""Migration 0003: the training_sessions table, up and down, with users kept."""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.cli import _alembic_config
from app.models import Role
from tests.conftest import make_settings
from tests.helpers import add_user


def test_0003_adds_and_removes_the_training_sessions_table(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    config = _alembic_config(settings)
    command.upgrade(config, "0002")
    add_user(settings, "keeper@unit.example", Role.trainee)
    engine = create_engine(settings.database_url)
    assert "training_sessions" not in inspect(engine).get_table_names()

    command.upgrade(config, "head")
    inspector = inspect(engine)
    columns = {c["name"]: c for c in inspector.get_columns("training_sessions")}
    assert set(columns) == {
        "id",
        "user_id",
        "scenario_id",
        "scenario_version",
        "seed",
        "status",
        "created_at",
        "started_at",
        "ended_at",
        "ticks",
        "final_state_hash",
        "event_head",
        "event_count",
        "record",
    }
    assert columns["record"]["nullable"] and not columns["seed"]["nullable"]
    assert [i["column_names"] for i in inspector.get_indexes("training_sessions")] == [["user_id"]]
    (fk,) = inspector.get_foreign_keys("training_sessions")
    assert fk["referred_table"] == "users" and fk["options"].get("ondelete") == "CASCADE"

    with engine.begin() as conn:  # a 63-bit seed must fit
        user = conn.execute(text("SELECT id FROM users")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO training_sessions (id, user_id, scenario_id, scenario_version, seed,"
                " status, created_at) VALUES ('s1', :u, 'x', '1.0.0', :seed, 'lobby', '2026-01-01')"
            ),
            {"u": user, "seed": 2**63 - 1},
        )
        assert conn.execute(
            text("SELECT seed, ticks, event_count FROM training_sessions")
        ).one() == (
            2**63 - 1,
            0,
            0,
        )

    command.downgrade(config, "0002")
    assert "training_sessions" not in inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT email FROM users")).scalar_one() == "keeper@unit.example"
    command.upgrade(config, "head")
    assert "training_sessions" in inspect(create_engine(settings.database_url)).get_table_names()
