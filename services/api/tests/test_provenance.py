"""Pack versions: the lock that fails when a pack changes without a bump, and the versions a stored
session and its score record."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli import cli
from app.contracts import SessionRecord, SessionScore
from app.contracts.common import PackRef
from app.contracts.paths import packs_root
from app.models import TrainingSession
from app.scoring import score_session
from sim import replay
from sim.provenance import (
    KINDS,
    LOCK_NAME,
    VersionMismatch,
    check_recorded,
    content_hash,
    current_entries,
    lock_problems,
    read_lock,
    refresh_lock,
    used_versions,
)

from .live_helpers import harrier_spec
from .live_support import login
from .scoring_support import baseline
from .test_live_rest import play

runner = CliRunner()
RADAR = "radar-generic-s.v1.yaml"


@pytest.fixture
def packs(tmp_path: Path) -> Path:
    """A copy of the lockable packs and their lock, for tests that edit them."""
    root = packs_root()
    for directory, _ in KINDS.values():
        shutil.copytree(root / directory, tmp_path / directory)
    shutil.copy(root / LOCK_NAME, tmp_path / LOCK_NAME)
    return tmp_path


def edit(root: Path, name: str, old: str, new: str, *, kind: str = "sensor-profiles") -> None:
    path = root / kind / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ----------------------------------------------------------------------------- the lock


def test_the_shipped_lock_matches_every_pack() -> None:
    assert lock_problems() == []


def test_the_lock_covers_every_sensor_profile_threat_class_and_rule_pack() -> None:
    keys = set(read_lock())
    assert keys == set(current_entries())
    for kind in KINDS:
        assert any(key.startswith(f"{kind}/") for key in keys)
    assert len([k for k in keys if k.startswith("sensor-profile/")]) == 6
    assert len([k for k in keys if k.startswith("threat-class/")]) == 11


def test_a_profile_changed_without_a_version_bump_fails(packs: Path) -> None:
    edit(packs, RADAR, "instrumented_range: { value: 4600", "instrumented_range: { value: 4700")
    (problem,) = lock_problems(packs)
    assert "sensor-profile/radar-generic-s" in problem
    assert "content changed" in problem and "bump the version" in problem


def test_a_threat_class_changed_without_a_version_bump_fails(packs: Path) -> None:
    edit(packs, "bird.v1.yaml", "max_speed: { value: 18", "max_speed: { value: 19", kind="threats")
    (problem,) = lock_problems(packs)
    assert problem.startswith("threat-class/bird: content changed")


def test_a_rule_pack_changed_without_a_version_bump_fails(packs: Path) -> None:
    path = packs / "rule-packs" / "training-baseline.v1.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("title:", "# changed below\ntitle:", 1), encoding="utf-8")
    assert lock_problems(packs) == []  # a comment is not content
    path.write_text(text.replace("en: ", "en: X", 1), encoding="utf-8")
    (problem,) = lock_problems(packs)
    assert problem.startswith("rule-pack/training-baseline: content changed")


def test_comments_and_formatting_are_not_content(packs: Path) -> None:
    path = packs / "sensor-profiles" / RADAR
    path.write_text("# a new comment\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    assert lock_problems(packs) == []


def test_the_refresh_refuses_new_content_under_the_old_version(packs: Path) -> None:
    edit(packs, RADAR, "instrumented_range: { value: 4600", "instrumented_range: { value: 4700")
    with pytest.raises(ValueError, match="radar-generic-s: content changed under version 0.3.0"):
        refresh_lock(packs)
    assert lock_problems(packs)  # nothing was written


def test_a_bump_then_a_refresh_clears_the_problem(packs: Path) -> None:
    edit(packs, RADAR, "instrumented_range: { value: 4600", "instrumented_range: { value: 4700")
    edit(packs, RADAR, "version: 0.3.0", "version: 0.4.0")
    (problem,) = lock_problems(packs)
    assert "version is 0.4.0 but" in problem and "has 0.3.0" in problem
    assert refresh_lock(packs) == ["sensor-profile/radar-generic-s: 0.3.0 to 0.4.0"]
    assert lock_problems(packs) == []
    assert read_lock(packs)["sensor-profile/radar-generic-s"]["version"] == "0.4.0"
    assert refresh_lock(packs) == []


def test_the_refresh_refuses_a_lower_version(packs: Path) -> None:
    edit(packs, RADAR, "version: 0.3.0", "version: 0.2.0")
    with pytest.raises(ValueError, match="version went down, 0.3.0 to 0.2.0"):
        refresh_lock(packs)


def test_a_missing_or_extra_entry_is_reported_and_a_refresh_fixes_it(packs: Path) -> None:
    lock = json.loads((packs / LOCK_NAME).read_text(encoding="utf-8"))
    del lock["entries"]["threat-class/kite"]
    lock["entries"]["threat-class/ghost"] = {"version": "1.0.0", "content_sha256": "0" * 64}
    (packs / LOCK_NAME).write_text(json.dumps(lock), encoding="utf-8")
    problems = lock_problems(packs)
    assert any("threat-class/kite: not in" in p for p in problems)
    assert any("threat-class/ghost: in" in p and "gone" in p for p in problems)
    changes = refresh_lock(packs)
    assert "threat-class/kite: added at 1.0.0" in changes
    assert "threat-class/ghost: removed" in changes
    assert lock_problems(packs) == []


def test_a_missing_lock_file_is_a_problem_per_pack(packs: Path) -> None:
    (packs / LOCK_NAME).unlink()
    assert read_lock(packs) == {}
    assert len(lock_problems(packs)) == len(current_entries(packs))


def test_the_hash_ignores_the_version_only() -> None:
    from app.contracts.loader import load_pack
    from app.contracts.sensor_profile import SensorProfile

    pack = load_pack(packs_root() / "sensor-profiles" / RADAR)
    assert isinstance(pack, SensorProfile)
    assert content_hash(pack) == content_hash(pack.model_copy(update={"version": "9.9.9"}))
    assert content_hash(pack) != content_hash(pack.model_copy(update={"fictional": False}))


def test_the_pack_lock_command(packs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACKS_DIR", str(packs))
    ok = runner.invoke(cli, ["pack-lock", "--check"])
    assert ok.exit_code == 0
    assert "up to date" in runner.invoke(cli, ["pack-lock"]).output
    edit(packs, RADAR, "instrumented_range: { value: 4600", "instrumented_range: { value: 4700")
    checked = runner.invoke(cli, ["pack-lock", "--check"])
    assert checked.exit_code == 1 and "content changed" in checked.output
    refused = runner.invoke(cli, ["pack-lock"])
    assert refused.exit_code == 1 and "bump it" in refused.output
    edit(packs, RADAR, "version: 0.3.0", "version: 0.3.1")
    done = runner.invoke(cli, ["pack-lock"])
    assert done.exit_code == 0 and "0.3.0 to 0.3.1" in done.output
    assert runner.invoke(cli, ["pack-lock", "--check"]).exit_code == 0


# ----------------------------------------------------------------------------- what a session used


def test_wave_8_changed_every_sensor_profile_so_none_is_still_at_its_first_version() -> None:
    versions = {k: v["version"] for k, v in current_entries().items() if k.startswith("sensor")}
    assert versions == {
        "sensor-profile/acoustic-generic-array": "1.1.0",
        "sensor-profile/eo-generic-day": "0.2.0",
        "sensor-profile/eo-generic-nv": "0.2.0",
        "sensor-profile/ir-generic-thermal": "0.2.0",
        "sensor-profile/radar-generic-s": "0.3.0",
        "sensor-profile/rf-generic-passive": "1.1.0",
    }


def test_used_versions_are_the_pinned_profiles_and_the_classes_flown() -> None:
    used = used_versions(harrier_spec())
    assert [(r.id, r.version) for r in used.profiles] == [
        ("eo-generic-day", "0.2.0"),
        ("radar-generic-s", "0.3.0"),
        ("rf-generic-passive", "1.1.0"),
    ]
    assert [(r.id, r.version) for r in used.threat_classes] == [
        ("bird", "1.0.0"),
        ("rotary-small", "1.0.0"),
    ]


def test_a_run_with_a_picture_records_the_versions_and_a_run_without_one_does_not() -> None:
    spec = harrier_spec()
    _, with_picture = replay.run(spec, 1, [], 20, picture=True)
    used = used_versions(spec)
    assert with_picture.profiles == list(used.profiles)
    assert with_picture.threat_classes == list(used.threat_classes)
    _, bare = replay.run(spec, 1, [], 20)
    assert bare.profiles == [] and bare.threat_classes == []


def test_a_replay_with_the_same_versions_matches_and_with_other_versions_is_refused() -> None:
    spec = harrier_spec()
    _, record = replay.run(spec, 1, [], 40, picture=True)
    assert replay.replay(spec, record).matches
    older = record.model_copy(
        update={"profiles": [PackRef(id="eo-generic-day", version="0.1.0"), *record.profiles[1:]]}
    )
    with pytest.raises(VersionMismatch, match="sensor profile versions"):
        replay.replay(spec, older)
    other = record.model_copy(update={"threat_classes": record.threat_classes[:-1]})
    with pytest.raises(VersionMismatch, match="threat class versions"):
        replay.replay(spec, other)


def test_a_record_made_before_versions_were_kept_is_not_checked() -> None:
    check_recorded(harrier_spec(), [], [])
    spec = harrier_spec()
    _, record = replay.run(spec, 1, [], 40, picture=True)
    legacy = record.model_copy(update={"profiles": [], "threat_classes": []})
    assert replay.replay(spec, legacy).matches


def test_a_score_carries_the_versions_of_its_record() -> None:
    spec = harrier_spec()
    _, record = replay.run(spec, 1, [], 40, picture=True, roe=True)
    score = score_session(spec, baseline(), record)
    assert score.profiles == record.profiles and score.threat_classes == record.threat_classes
    assert score.profiles
    legacy = record.model_copy(update={"profiles": [], "threat_classes": []})
    assert score_session(spec, baseline(), legacy).profiles == []


def test_a_stored_session_and_its_score_record_the_profile_versions_they_used(
    live_client: TestClient,
) -> None:
    csrf = login(live_client)
    row = play(live_client, csrf, ticks=300)
    with Session(live_client.app.state.engine) as db:  # type: ignore[attr-defined]
        stored = db.get(TrainingSession, row["id"])
        assert stored is not None and stored.record is not None and stored.score is not None
        record = SessionRecord.model_validate_json(stored.record)
        score = SessionScore.model_validate_json(stored.score)
    used = used_versions(harrier_spec())
    assert record.profiles == list(used.profiles) and record.threat_classes
    assert score.profiles == record.profiles and score.threat_classes == record.threat_classes
    body = live_client.get(f"/api/v1/sessions/{row['id']}/score").json()
    assert [(p["id"], p["version"]) for p in body["profiles"]] == [
        (r.id, r.version) for r in used.profiles
    ]
