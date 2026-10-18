"""What a trainee may see of the event log and of each frame: no ground truth, anywhere."""

import json

from app.contracts import ActionRecord, EventRecord
from sim import replay
from sim.audience import TRAINEE_EVENTS, trainee_event
from sim.tracking.picture import TRUTH_EVENT_TYPES
from tests.live_helpers import ACTOR, harrier_spec, harrier_world, run_until_track

FORBIDDEN = ("contact-", "truth", "true_class", "disposition", "correct_flag", "ledger")


def record(kind: str, payload: dict[str, object], actor: str = "sim") -> EventRecord:
    return EventRecord(
        seq=3, t=1.5, type=kind, actor=actor, payload=payload,
        prev_hash="0" * 64, hash="1" * 64,
    )  # fmt: skip


def test_truth_events_never_reach_a_trainee() -> None:
    for kind in sorted(TRUTH_EVENT_TYPES | {"threat.spawn", "threat.despawn", "weather.set"}):
        assert trainee_event(record(kind, {"id": "contact-quad"})) is None, kind


def test_the_real_drone_behind_an_operator_action_is_stripped() -> None:
    event = trainee_event(
        record("action.classify", {"track": "T7", "class_id": "bird", "target": "contact-quad"},
               "trainee:t-1")
    )  # fmt: skip
    assert event is not None
    assert event["payload"] == {"track": "T7", "class_id": "bird"}


def test_a_rejection_that_echoes_a_payload_is_stripped_too() -> None:
    event = trainee_event(
        record("action.rejected", {"action": "hold", "reason": "no live track 'T9'",
                                   "payload": {"track": "T9", "target": "contact-quad"}})
    )  # fmt: skip
    assert event is not None
    assert event["payload"]["payload"] == {"track": "T9"}


def test_the_allow_list_has_no_truth_type() -> None:
    assert not (TRAINEE_EVENTS & TRUTH_EVENT_TYPES)
    assert not any(kind.startswith(("threat.", "ledger.", "assist.")) for kind in TRAINEE_EVENTS)


def test_a_whole_session_shows_the_trainee_no_ground_truth() -> None:
    world = harrier_world()
    track = run_until_track(world, "contact-quad")
    assert world.picture is not None
    frames: list[str] = []
    for i in range(1200):
        actions = []
        if i == 10:
            actions = [ActionRecord(tick=world.tick, actor=ACTOR, action="classify",
                                    payload={"track": track, "class_id": "rotary-small"})]  # fmt: skip
        if i == 40:
            actions = [ActionRecord(tick=world.tick, actor=ACTOR, action="sensor-cue",
                                    payload={"sensor": "eo-1", "track": track, "narrow": True})]  # fmt: skip
        world.step(actions)
        frames.append(json.dumps(world.picture.trainee_frame(world.tick)))
    shown = [e for r in world.log.records if (e := trainee_event(r)) is not None]
    assert shown, "the session produced no trainee events"
    for text in [*frames, *(json.dumps(e) for e in shown)]:
        for word in FORBIDDEN:
            assert word not in text, word
    # ... while the full log does hold the truth, so the filter is doing real work
    assert any("contact-quad" in json.dumps(r.payload) for r in world.log.records)


def test_a_finished_session_record_filters_the_same_way() -> None:
    spec = harrier_spec()
    _, rec = replay.run(spec, spec.default_seed, [], 600, picture=True, roe=True)
    kinds = {e.type for e in rec.events}
    shown = {e["type"] for r in rec.events if (e := trainee_event(r)) is not None}
    assert "threat.spawn" in kinds and "threat.spawn" not in shown
    assert {"session.start", "session.end"} <= shown
