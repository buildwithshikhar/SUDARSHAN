"""Saved scenarios: the table, the store, the session catalogue's fallback to it and the lobby."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.cli import _alembic_config
from app.contracts import ScenarioSpec
from app.live.catalog import ScenarioCatalog
from app.models import Role, ScenarioRecord
from app.scenarios.store import ScenarioStore, spec_sha256
from tests.conftest import make_settings
from tests.helpers import add_user

from .live_helpers import harrier_spec
from .live_support import create_session, login


def saved_spec(scenario_id: str = "saved-one", **meta: Any) -> ScenarioSpec:
    data = harrier_spec().model_dump(mode="json")
    data["id"] = scenario_id
    data["meta"] = {"origin": "authored", "tags": ["test"], **meta}
    return ScenarioSpec.model_validate(data)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    settings = make_settings(tmp_path)
    command.upgrade(_alembic_config(settings), "head")
    engine = create_engine(settings.database_url)
    yield sessionmaker(engine)
    engine.dispose()


# ----------------------------------------------------------------------------- migration


def test_0005_adds_and_removes_the_scenario_records_table(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    config = _alembic_config(settings)
    command.upgrade(config, "0004")
    add_user(settings, "author@unit.example", Role.instructor)
    engine = create_engine(settings.database_url)
    assert "scenario_records" not in inspect(engine).get_table_names()

    command.upgrade(config, "0005")
    inspector = inspect(engine)
    columns = {c["name"]: c for c in inspector.get_columns("scenario_records")}
    assert set(columns) == {
        "id",
        "version",
        "owner_id",
        "origin",
        "spec",
        "spec_sha256",
        "yaml",
        "request",
        "code",
        "checks",
        "features",
        "created_at",
    }
    assert columns["owner_id"]["nullable"] and not columns["spec"]["nullable"]
    (fk,) = inspector.get_foreign_keys("scenario_records")
    assert fk["referred_table"] == "users" and fk["options"].get("ondelete") == "SET NULL"
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1

    command.downgrade(config, "0004")
    assert "scenario_records" not in inspect(engine).get_table_names()
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1


# ----------------------------------------------------------------------------- the store


def test_a_saved_scenario_reads_back_exactly(factory: sessionmaker[Session]) -> None:
    store = ScenarioStore(factory)
    spec = saved_spec()
    put = store.put(
        spec,
        owner_id=None,
        origin="authored",
        yaml="id: saved-one\n",
        request={"seed": 1},
        code="SD1-ABCD",
        checks=[{"name": "x", "passed": True}],
        features={"threat_count": 0.5},
    )
    got = store.get("saved-one")
    assert got is not None and got == put
    assert got.spec == spec and got.spec_sha256 == spec_sha256(spec)
    assert (got.yaml, got.request, got.code) == ("id: saved-one\n", {"seed": 1}, "SD1-ABCD")
    assert got.checks == [{"name": "x", "passed": True}] and got.features == {"threat_count": 0.5}
    assert store.get("nothing") is None


def test_putting_the_same_id_again_replaces_the_row(factory: sessionmaker[Session]) -> None:
    store = ScenarioStore(factory)
    store.put(saved_spec(tags=[]), owner_id=None, origin="authored", yaml="one")
    changed = saved_spec(difficulty=70)
    store.put(changed, owner_id=None, origin="generated", yaml="two", checks=[])
    (only,) = store.all()
    assert only.spec == changed and only.yaml == "two" and only.origin == "generated"
    assert only.request is None and only.checks == []


def test_all_lists_by_id_and_delete_removes(factory: sessionmaker[Session]) -> None:
    store = ScenarioStore(factory)
    for name in ("b-two", "a-one"):
        store.put(saved_spec(name), owner_id=None, origin="authored")
    assert [s.spec.id for s in store.all()] == ["a-one", "b-two"]
    assert store.delete("a-one") is True and store.delete("a-one") is False
    assert [s.spec.id for s in store.all()] == ["b-two"]


def test_a_row_edited_outside_the_application_is_refused(
    factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    store = ScenarioStore(factory)
    store.put(saved_spec(), owner_id=None, origin="authored")
    with factory() as db:
        row = db.get(ScenarioRecord, "saved-one")
        assert row is not None
        row.spec = row.spec.replace('"duration_s": 420.0', '"duration_s": 430.0')
        db.commit()
    assert store.get("saved-one") is None and store.all() == []
    assert "unreadable" in caplog.text
    with factory() as db:
        row = db.get(ScenarioRecord, "saved-one")
        assert row is not None
        row.spec = "{not json"
        db.commit()
    assert store.get("saved-one") is None


# ----------------------------------------------------------------------------- the catalogue


def test_the_catalogue_falls_back_to_saved_scenarios(factory: sessionmaker[Session]) -> None:
    store = ScenarioStore(factory)
    catalog = ScenarioCatalog(saved=store)
    assert catalog.get("saved-one") is None
    store.put(saved_spec(), owner_id=None, origin="authored")
    entry = catalog.get("saved-one", "1.0.0")
    assert entry is not None and entry.spec.id == "saved-one"
    assert catalog.get("saved-one", "9.9.9") is None
    assert "saved-one" not in catalog.entries()  # the pack list is only the packs
    assert "saved-one" in catalog.all_entries() and "harrier-morning-watch" in catalog.all_entries()
    assert catalog.get("saved-one") is catalog.get("saved-one")  # built once per content


def test_a_pack_scenario_is_never_shadowed_by_a_saved_one(factory: sessionmaker[Session]) -> None:
    store = ScenarioStore(factory)
    store.put(saved_spec("harrier-morning-watch"), owner_id=None, origin="authored")
    catalog = ScenarioCatalog(saved=store)
    entry = catalog.get("harrier-morning-watch")
    assert (
        entry is not None and entry.spec.meta is not None and entry.spec.meta.origin == "scripted"
    )
    assert catalog.all_entries()["harrier-morning-watch"].spec.meta.origin == "scripted"  # type: ignore[union-attr]


def test_a_saved_scenario_that_cannot_be_built_is_not_listed(
    factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    store = ScenarioStore(factory)
    data = harrier_spec().model_dump(mode="json")
    data["id"] = "saved-bad"
    data["rule_pack"] = {"id": "no-such-pack", "version": "1.0.0"}
    store.put(ScenarioSpec.model_validate(data), owner_id=None, origin="authored")
    catalog = ScenarioCatalog(saved=store)
    assert catalog.get("saved-bad") is None and "saved-bad" not in catalog.all_entries()
    assert "not playable" in caplog.text


def test_a_catalogue_without_a_store_lists_only_the_packs() -> None:
    catalog = ScenarioCatalog()
    assert catalog.saved_entries() == {} and catalog.get("saved-one") is None


# ----------------------------------------------------------------------------- the lobby


def keep(client: TestClient, spec: ScenarioSpec) -> None:
    ScenarioStore(client.app.state.session_factory).put(  # type: ignore[attr-defined]
        spec, owner_id=None, origin="authored"
    )


def test_a_saved_scenario_is_in_the_lobby_and_can_be_played(live_client: TestClient) -> None:
    keep(live_client, saved_spec("saved-lobby"))
    csrf = login(live_client)
    listed = {s["id"] for s in live_client.get("/api/v1/scenarios").json()}
    assert {"saved-lobby", "harrier-morning-watch"} <= listed
    row = create_session(live_client, csrf, scenario="saved-lobby")
    assert row["scenario_id"] == "saved-lobby"


def test_a_scenario_that_is_not_playable_is_hidden_and_refused(live_client: TestClient) -> None:
    keep(live_client, saved_spec("saved-hidden", playable=False))
    csrf = login(live_client)
    assert "saved-hidden" not in {s["id"] for s in live_client.get("/api/v1/scenarios").json()}
    response = live_client.post(
        "/api/v1/sessions", json={"scenario_id": "saved-hidden"}, headers=csrf
    )
    assert response.status_code == 409 and "not playable" in response.json()["detail"]
