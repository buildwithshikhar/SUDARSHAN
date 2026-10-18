"""Operator actions on tracks: ROE verdicts, effects, logging, determinism and replay."""

import pytest

from app.contracts import ActionRecord
from sim import replay
from sim.world import ActionError, World
from tests.live_helpers import (
    ACTOR,
    act,
    events,
    harrier_spec,
    harrier_world,
    run_until_track,
)


@pytest.fixture(scope="module")
def quad_world() -> tuple[World, str]:
    world = harrier_world()
    track = run_until_track(world, "contact-quad")
    return world, track


def fresh(quad_world: tuple[World, str]) -> tuple[World, str]:
    """A copy of the world at the moment the quad is first tracked."""
    world, track = quad_world
    spec = harrier_spec()
    from sim.roe import load_rule_engine
    from sim.tracking.picture import Picture

    copy = World.restore(
        spec,
        world.snapshot(),
        picture=Picture.build(spec, world.seed),
        roe=load_rule_engine(spec),
    )
    return copy, track


def test_a_response_the_rules_forbid_is_blocked_with_the_rule_and_its_version(
    quad_world: tuple[World, str],
) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, "engage", track=track, effector_class="ec-a")])
    [verdict] = events(world, "roe.verdict")
    assert verdict["permitted"] is False
    assert verdict["code"] == "conditions"  # the operator has not assessed the track
    assert verdict["rule_id"] == "suspect-outer-zone"
    assert verdict["pack_version"] == "1.0.0"
    assert isinstance(verdict["rule_title"], dict) and "en" in verdict["rule_title"]
    assert events(world, "action.engage") == []


def test_after_classify_and_assess_the_same_response_is_permitted(
    quad_world: tuple[World, str],
) -> None:
    world, track = fresh(quad_world)
    # wait for a confident class estimate so the rule's confidence floor (0.6) is met
    assert world.picture is not None
    for _ in range(400):
        if world.picture.tracker.tracks[track].class_estimate()[1] >= 0.6:
            break
        world.step()
    world.step([act(world, "classify", track=track, class_id="rotary-small")])
    world.step([act(world, "assess", track=track, identity="hostile")])
    world.step([act(world, "engage", track=track, effector_class="ec-a")])
    verdicts = events(world, "roe.verdict")
    assert [v["action"] for v in verdicts] == ["classify", "assess", "engage"]
    engage = verdicts[-1]
    context = engage["context"]
    assert isinstance(context, dict)
    assert context["identity"] == "hostile" and context["classification"] == "rotary-small"
    assert context["zone_role"] == "outer"
    assert (engage["permitted"], engage["rule_id"]) == (True, "suspect-outer-zone")
    [logged] = events(world, "action.engage")
    assert logged["effector_class"] == "ec-a" and logged["target"] == "contact-quad"


def test_a_permitted_action_is_logged_with_the_real_drone_behind_the_track(
    quad_world: tuple[World, str],
) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, "classify", track=track, class_id="rotary-small")])
    [logged] = events(world, "action.classify")
    assert logged == {"track": track, "class_id": "rotary-small", "target": "contact-quad"}
    drone = next(d for d in world.drones if d.id == "contact-quad")
    assert drone.assigned_class == "rotary-small"


def test_hold_is_always_permitted_and_is_remembered(quad_world: tuple[World, str]) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, "hold", track=track)])
    assert events(world, "roe.verdict")[-1]["permitted"] is True
    assert world.operator[track] == {"held": True}


@pytest.mark.parametrize(
    ("action", "payload", "message"),
    [
        ("classify", {"class_id": "dragon"}, "class_id"),
        ("assess", {"identity": "ally"}, "identity"),
        ("engage", {}, "effector_class"),
        ("engage", {"effector_class": "ec-z"}, "no effector class"),
        ("hold", {"target": "contact-quad"}, "does not take target"),
    ],
)
def test_malformed_operator_actions_are_rejected_not_applied(
    quad_world: tuple[World, str], action: str, payload: dict[str, object], message: str
) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, action, track=track, **payload)])
    [rejected] = events(world, "action.rejected")
    assert message in str(rejected["reason"])
    assert events(world, "roe.verdict") == []


def test_an_unknown_track_is_rejected(quad_world: tuple[World, str]) -> None:
    world, _ = fresh(quad_world)
    world.step([act(world, "hold", track="T9999")])
    [rejected] = events(world, "action.rejected")
    assert "no live track" in str(rejected["reason"])


def test_a_classification_of_a_false_alarm_track_is_logged_without_a_target(
    quad_world: tuple[World, str],
) -> None:
    world, _ = fresh(quad_world)
    assert world.picture is not None
    false_track = next(
        (t for t in world.picture.tracker.tracks if world.picture.ledger.identity_of(t) is None),
        None,
    )
    if false_track is None:
        pytest.skip("no track without a ground-truth identity at this tick")
    world.step([act(world, "classify", track=false_track, class_id="bird")])
    assert events(world, "action.classify")[-1]["target"] is None


def test_assessments_of_vanished_tracks_are_forgotten(quad_world: tuple[World, str]) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, "assess", track=track, identity="hostile")])
    world.operator["T-gone"] = {"identity": "friend"}
    world.step([act(world, "hold", track=track)])
    assert "T-gone" not in world.operator


def test_a_world_with_rules_needs_a_picture() -> None:
    from sim.roe import load_rule_engine

    spec = harrier_spec()
    with pytest.raises(ValueError, match="sensor picture"):
        World(spec, 1, roe=load_rule_engine(spec))


def test_operator_actions_without_a_picture_are_rejected() -> None:
    world = World(harrier_spec(), 1)
    world.step([ActionRecord(tick=0, actor=ACTOR, action="hold", payload={"track": "T001"})])
    [rejected] = events(world, "action.rejected")
    assert "no sensor picture" in str(rejected["reason"])


def test_a_picture_without_rules_applies_actions_with_no_verdict() -> None:
    from sim.tracking.picture import Picture

    spec = harrier_spec()
    world = World(spec, spec.default_seed, picture=Picture.build(spec, spec.default_seed))
    track = run_until_track(world, "contact-quad")
    world.step([act(world, "assess", track=track, identity="hostile")])
    assert events(world, "roe.verdict") == []
    assert events(world, "action.assess")


def test_operator_state_is_in_the_hash_only_with_rules(quad_world: tuple[World, str]) -> None:
    world, track = fresh(quad_world)
    before = world.state_hash()
    world.step([act(world, "assess", track=track, identity="hostile")])
    assert world.state()["operator"][track] == {"identity": "hostile"}
    assert world.state_hash() != before


def test_snapshot_and_restore_carry_the_operator_state(quad_world: tuple[World, str]) -> None:
    from sim.roe import load_rule_engine
    from sim.tracking.picture import Picture

    world, track = fresh(quad_world)
    world.step([act(world, "assess", track=track, identity="suspect")])
    spec = harrier_spec()
    again = World.restore(
        spec, world.snapshot(), picture=Picture.build(spec, world.seed), roe=load_rule_engine(spec)
    )
    assert again.operator == world.operator
    assert again.state_hash() == world.state_hash()
    with pytest.raises(ValueError, match="operator state"):
        World.restore(spec, world.snapshot(), picture=Picture.build(spec, world.seed))
    plain = World(spec, 1)
    with pytest.raises(ValueError, match="no operator state"):
        World.restore(spec, plain.snapshot(), roe=load_rule_engine(spec))


def test_a_session_with_operator_actions_replays_exactly() -> None:
    spec = harrier_spec()
    probe = harrier_world()
    track = run_until_track(probe, "contact-quad")
    tick = probe.tick
    actions = [
        ActionRecord(tick=tick, actor=ACTOR, action="classify",
                     payload={"track": track, "class_id": "rotary-small"}),
        ActionRecord(tick=tick + 5, actor=ACTOR, action="assess",
                     payload={"track": track, "identity": "hostile"}),
        ActionRecord(tick=tick + 10, actor=ACTOR, action="engage",
                     payload={"track": track, "effector_class": "ec-a"}),
        ActionRecord(tick=tick + 12, actor=ACTOR, action="sensor-cue",
                     payload={"sensor": "eo-1", "track": track, "narrow": True}),
        ActionRecord(tick=tick + 14, actor=ACTOR, action="track-relabel",
                     payload={"track": track, "label": "HOSTILE-1"}),
    ]  # fmt: skip
    _, record = replay.run(spec, spec.default_seed, actions, tick + 100, picture=True, roe=True)
    assert record.roe and record.picture
    assert {e.type for e in record.events} >= {"roe.verdict", "action.classify", "sensor.cue"}
    result = replay.replay(spec, record)
    assert result.matches and result.first_divergent_seq is None


def test_a_picture_only_session_record_still_replays_without_rules() -> None:
    spec = harrier_spec()
    _, record = replay.run(spec, 5, [], 100, picture=True)
    assert not record.roe
    assert replay.replay(spec, record).matches


def test_applying_an_action_for_the_wrong_tick_is_still_refused() -> None:
    world = harrier_world()
    with pytest.raises(ActionError, match="applied at tick"):
        world.step([ActionRecord(tick=3, actor=ACTOR, action="hold", payload={"track": "T001"})])


def test_designating_a_track_marks_the_real_drone_and_the_track(
    quad_world: tuple[World, str],
) -> None:
    world, track = fresh(quad_world)
    world.step([act(world, "designate", track=track)])
    assert world.operator[track] == {"designated": True}
    assert next(d for d in world.drones if d.id == "contact-quad").designated
