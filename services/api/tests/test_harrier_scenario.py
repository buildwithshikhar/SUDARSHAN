"""The scripted wave 5 scenario: what it contains, and that an oracle defender can solve it."""

import pytest

from app.contracts import ActionRecord
from sim import replay
from tests.live_helpers import ACTOR, events, harrier_spec, harrier_world

SPEC = harrier_spec()


def test_the_scenario_is_the_scripted_day_slice() -> None:
    assert SPEC.fictional
    assert SPEC.world.terrain.kind == "flat"
    assert 8 <= SPEC.world.start_time_of_day_h <= 16  # daylight
    by_disposition = {d: [t.id for t in SPEC.threats if t.disposition == d] for d in
                      ("hostile", "civil-permitted", "clutter")}  # fmt: skip
    assert len(by_disposition["hostile"]) == 1
    assert len(by_disposition["civil-permitted"]) == 1
    assert len(by_disposition["clutter"]) >= 3
    assert {t.class_id for t in SPEC.threats if t.disposition == "clutter"} == {"bird"}
    assert {s.profile.id for s in SPEC.sensors} == {
        "radar-generic-s",
        "eo-generic-day",
        "rf-generic-passive",
    }


def test_a_filed_flight_covers_the_permitted_civil_drone_and_not_the_hostile_one() -> None:
    [flight] = SPEC.filed_flights
    civil = next(t for t in SPEC.threats if t.disposition == "civil-permitted")
    hostile = next(t for t in SPEC.threats if t.disposition == "hostile")

    def inside(x: float, y: float) -> bool:
        return (x - flight.center.x) ** 2 + (y - flight.center.y) ** 2 <= flight.radius_m**2

    assert all(inside(w.position.x, w.position.y) for w in civil.route)
    assert not any(inside(w.position.x, w.position.y) for w in hostile.route)
    assert flight.from_s <= civil.spawn_s <= flight.to_s


def test_every_text_has_english_and_hindi() -> None:
    for text in (
        SPEC.title,
        SPEC.summary,
        *(t.label for t in SPEC.threats),
        *(f.label for f in SPEC.filed_flights),
    ):
        assert text.en.strip() and text.hi.strip()


def test_an_oracle_defender_solves_the_scenario_by_the_rules() -> None:
    """Verified solvable by test run: with ground truth, the right calls are possible and the
    rules permit exactly the right response (never a response on the civil drone or a bird)."""
    world = harrier_world()
    assert world.picture is not None
    done: dict[str, set[str]] = {}
    permitted_engage: list[str] = []
    blocked_civil: list[str] = []
    for _ in range(20 * 360):
        actions: list[ActionRecord] = []
        picture = world.picture
        if world.tick % 20 == 0:
            for track_id, track in sorted(picture.tracker.tracks.items()):
                truth = picture.ledger.identity_of(track_id)
                if track.status != "confirmed" or truth is None:
                    continue
                steps = done.setdefault(track_id, set())
                drone = next(d for d in SPEC.threats if d.id == truth)
                identity = {"hostile": "hostile", "civil-permitted": "neutral",
                            "clutter": "neutral"}[drone.disposition]  # fmt: skip
                if "cue" not in steps:
                    steps.add("cue")
                    actions.append(ActionRecord(tick=world.tick, actor=ACTOR, action="sensor-cue",
                                                payload={"sensor": "eo-1", "track": track_id, "narrow": True}))  # fmt: skip
                elif "classify" not in steps:
                    steps.add("classify")
                    actions.append(ActionRecord(tick=world.tick, actor=ACTOR, action="classify",
                                                payload={"track": track_id, "class_id": drone.class_id}))  # fmt: skip
                elif "assess" not in steps:
                    steps.add("assess")
                    actions.append(ActionRecord(tick=world.tick, actor=ACTOR, action="assess",
                                                payload={"track": track_id, "identity": identity}))  # fmt: skip
                elif "respond" not in steps and track.class_estimate()[1] >= 0.6:
                    steps.add("respond")
                    if drone.disposition == "hostile":
                        actions.append(ActionRecord(tick=world.tick, actor=ACTOR, action="engage",
                                                    payload={"track": track_id, "effector_class": "ec-a"}))  # fmt: skip
                    else:
                        # a permitted civil drone: even trying to engage must be blocked
                        actions.append(ActionRecord(tick=world.tick, actor=ACTOR, action="engage",
                                                    payload={"track": track_id, "effector_class": "ec-a"}))  # fmt: skip
                        blocked_civil.append(track_id)
                if actions:
                    break
        world.step(actions)
    verdicts = events(world, "roe.verdict")
    engages = [v for v in verdicts if v["action"] == "engage"]
    permitted_engage = [str(v["track"]) for v in engages if v["permitted"]]
    assert permitted_engage, "the oracle never got a permitted response on the hostile drone"
    for v in engages:
        tid = str(v["track"])
        truths = {
            r.payload.get("target")
            for r in world.log.records
            if r.type == "action.assess" and r.payload.get("track") == tid
        }
        if v["permitted"]:
            assert truths <= {"contact-quad"}, "a response was permitted on something harmless"
    assert blocked_civil, "the oracle never tried the civil drone"
    assert all(not v["permitted"] for v in engages if v["track"] in blocked_civil)
    assert world.picture is not None


@pytest.mark.parametrize("seed", [1, 7, 260118])
def test_the_hostile_drone_is_tracked_and_confident_enough_to_engage_for_every_seed(
    seed: int,
) -> None:
    world = harrier_world(seed)
    assert world.picture is not None
    first_confident: int | None = None
    for _ in range(20 * 360):
        world.step()
        for track_id, track in world.picture.tracker.tracks.items():
            if (
                track.status == "confirmed"
                and world.picture.ledger.identity_of(track_id) == "contact-quad"
                and track.class_estimate()[1] >= 0.6
            ):
                first_confident = world.tick
        if first_confident is not None:
            break
    assert first_confident is not None, f"seed {seed}: never confident about the hostile drone"
    assert first_confident / 20 < 300


def test_the_same_seed_and_actions_replay_to_the_same_hash() -> None:
    _, a = replay.run(SPEC, 3, [], 800, picture=True, roe=True)
    _, b = replay.run(SPEC, 3, [], 800, picture=True, roe=True)
    assert a.final_state_hash == b.final_state_hash
