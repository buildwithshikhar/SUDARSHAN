"""The ground truth the scorer needs, and that a trainee never sees: first reports, the target of
each action and verdict, and what a contact report is graded against."""

import pytest

from app.contracts import EventRecord
from sim.audience import trainee_event
from sim.world import World
from tests.live_helpers import act, events, harrier_spec, harrier_world, run_until_track

FULL_REPORT = {
    "class_id": "rotary-small",
    "count": 1,
    "bearing_deg": 25.0,
    "range_m": 1800,
    "heading_deg": 200.0,
    "confidence": 0.8,
}


@pytest.fixture(scope="module")
def quad() -> tuple[World, str]:
    world = harrier_world()
    return world, run_until_track(world, "contact-quad")


def fresh(quad: tuple[World, str]) -> tuple[World, str]:
    from sim.roe import load_rule_engine
    from sim.tracking.picture import Picture

    world, track = quad
    spec = harrier_spec()
    copy = World.restore(
        spec,
        world.snapshot(),
        picture=Picture.build(spec, world.seed),
        roe=load_rule_engine(spec),
    )
    return copy, track


def test_each_drone_gets_one_first_report_event_when_a_sensor_first_reports_it() -> None:
    world = harrier_world()
    for _ in range(20 * 120):
        world.step()
    firsts = events(world, "ledger.first_report")
    drones = [str(e["drone"]) for e in firsts]
    assert len(drones) == len(set(drones)) and drones
    assert all(e["sensor"] and e["modality"] for e in firsts)
    spawn_t = {r.payload["id"]: r.t for r in world.log.records if r.type == "threat.spawn"}
    for record in world.log.records:
        if record.type == "ledger.first_report":
            assert record.t >= spawn_t[record.payload["drone"]]


def test_the_first_report_state_survives_a_snapshot(quad: tuple[World, str]) -> None:
    world, _ = fresh(quad)
    seen = set(world.picture._first_seen)
    assert "contact-quad" in seen
    world.step()
    assert not [e for e in events(world, "ledger.first_report") if e["drone"] in seen][len(seen) :]


def test_a_verdict_and_a_cue_name_the_real_drone_for_scoring(quad: tuple[World, str]) -> None:
    world, track = fresh(quad)
    world.step([act(world, "engage", track=track, effector_class="ec-a")])
    assert events(world, "roe.verdict")[-1]["target"] == "contact-quad"
    world.step([act(world, "sensor-cue", sensor="eo-1", track=track, narrow=True)])
    assert events(world, "action.sensor_cue")[-1]["target"] == "contact-quad"


def test_a_filed_report_logs_what_it_is_graded_against(quad: tuple[World, str]) -> None:
    world, track = fresh(quad)
    drone = next(d for d in world.drones if d.id == "contact-quad")
    where = (round(drone.x, 3), round(drone.y, 3))  # the report is applied before the drones move
    world.step([act(world, "report", track=track, **FULL_REPORT)])
    [logged] = events(world, "action.report")
    truth = logged["truth"]
    assert isinstance(truth, dict)
    assert truth["class_id"] == "rotary-small" and truth["disposition"] == "hostile"
    assert truth["count"] == 1
    assert (truth["x"], truth["y"]) == where
    assert 0 <= float(truth["heading_deg"]) < 360  # type: ignore[arg-type]
    assert logged["class_id"] == "rotary-small" and logged["count"] == 1


def test_a_report_on_a_false_track_has_a_target_of_none_and_no_truth(
    quad: tuple[World, str],
) -> None:
    world, _ = fresh(quad)
    assert world.picture is not None
    false_track = next(
        (t for t in world.picture.tracker.tracks if world.picture.ledger.identity_of(t) is None),
        None,
    )
    if false_track is None:
        pytest.skip("no false track at this tick")
    world.step([act(world, "report", track=false_track)])
    [logged] = events(world, "action.report")
    assert logged["target"] is None and "truth" not in logged


def test_the_count_in_a_report_is_the_flock_around_the_contact() -> None:
    world = harrier_world()
    track = run_until_track(world, "contact-bird-1", limit_s=300)
    world.step([act(world, "report", track=track)])
    truth = events(world, "action.report")[-1]["truth"]
    assert isinstance(truth, dict) and truth["class_id"] == "bird"
    assert 1 <= int(truth["count"]) <= 3  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"class_id": "dragon"}, "class_id"),
        ({"count": 0}, "count"),
        ({"count": 2.5}, "count"),
        ({"count": True}, "count"),
        ({"bearing_deg": 360}, "bearing_deg"),
        ({"bearing_deg": "north"}, "bearing_deg"),
        ({"heading_deg": -1}, "heading_deg"),
        ({"range_m": 60_000}, "range_m"),
        ({"confidence": 1.5}, "confidence"),
        ({"speed": 3}, "does not take"),
    ],
)
def test_a_malformed_report_is_rejected(
    quad: tuple[World, str], payload: dict[str, object], message: str
) -> None:
    world, track = fresh(quad)
    world.step([act(world, "report", track=track, **payload)])
    [rejected] = events(world, "action.rejected")
    assert message in str(rejected["reason"])
    assert events(world, "action.report") == []


def test_a_report_with_no_fields_is_still_accepted(quad: tuple[World, str]) -> None:
    world, track = fresh(quad)
    world.step([act(world, "report", track=track)])
    assert events(world, "action.report")


def test_a_trainee_never_sees_target_or_truth(quad: tuple[World, str]) -> None:
    world, track = fresh(quad)
    world.step([act(world, "report", track=track, **FULL_REPORT)])
    shown = {
        r.type: trainee_event(r)
        for r in world.log.records
        if r.type in ("action.report", "roe.verdict")
    }
    for event in shown.values():
        assert event is not None
        assert "target" not in event["payload"] and "truth" not in event["payload"]
    assert shown["action.report"]["payload"]["count"] == 1  # type: ignore[index]


def test_the_first_report_event_is_not_a_trainee_event() -> None:
    record = EventRecord(
        seq=2, t=1.0, type="ledger.first_report", actor="sim",
        payload={"drone": "contact-quad", "sensor": "radar-1", "modality": "radar"},
        prev_hash="0" * 64, hash="1" * 64,
    )  # fmt: skip
    assert trainee_event(record) is None
