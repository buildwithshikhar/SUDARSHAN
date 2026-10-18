"""Operator track commands: relabel, merge, split, drop; rejections change nothing."""

import json
from typing import Any

import pytest

from sim.sensors.detection import DATA_REFERENCE, DATA_VERIFIED
from sim.tracking import Tracker, commands
from sim.tracking.commands import ACTIONS, EVENT_TYPE, LABEL_MAX, REJECTED, CommandOutcome

from .tracking_cases import SWAP_SEED, SWAP_TICK, bare_track, bare_tracker, crossing


def snapshot(tracker: Tracker) -> str:
    return json.dumps(tracker.state(), sort_keys=True)


def assert_rejected(outcome: CommandOutcome, before: str, tracker: Tracker, text: str) -> None:
    assert not outcome.ok and outcome.effects == ()
    assert text in (outcome.reason or "")
    ((kind, payload),) = outcome.events
    assert kind == REJECTED and payload["reason"] == outcome.reason
    assert snapshot(tracker) == before  # a rejection changes nothing


def assert_event_types(outcome: CommandOutcome) -> None:
    assert outcome.events
    assert all(EVENT_TYPE.match(kind) for kind, _ in outcome.events)
    for _, payload in outcome.events:
        assert json.loads(json.dumps(payload)) == payload


# ---------------------------------------------------------------------------- relabel


def test_relabel_strips_the_name_and_reports_what_changed() -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed")
    out = commands.relabel(tracker, 10, "T001", "  ALPHA-1 ")
    assert out.ok and out.reason is None
    assert out.events == [
        ("track.relabel", {"track": "T001", "label": "ALPHA-1", "previous": "T001"})
    ]
    assert out.effects == (("relabel", "T001", "ALPHA-1"),)
    assert tracker.tracks["T001"].label == "ALPHA-1" and tracker.tracks["T002"].label == "T002"
    assert_event_types(out)


def test_a_label_is_one_to_twenty_four_printable_characters() -> None:
    tracker = bare_tracker(T001="confirmed")
    assert commands.relabel(tracker, 0, "T001", "x" * LABEL_MAX).ok
    before = snapshot(tracker)
    for bad in ("", "   ", "x" * (LABEL_MAX + 1)):
        out = commands.relabel(tracker, 0, "T001", bad)
        assert_rejected(out, before, tracker, "1 to 24 characters")
    assert_rejected(commands.relabel(tracker, 0, "T001", "a\tb"), before, tracker, "control")


def test_relabel_refuses_an_unknown_track_and_an_unchanged_name() -> None:
    tracker = bare_tracker(T001="confirmed")
    before = snapshot(tracker)
    assert_rejected(commands.relabel(tracker, 0, "T404", "X"), before, tracker, "no live track")
    assert_rejected(commands.relabel(tracker, 0, "T001", "T001"), before, tracker, "already")


def test_a_name_another_track_wears_needs_an_exchange() -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed")
    before = snapshot(tracker)
    out = commands.relabel(tracker, 0, "T001", "T002")
    assert_rejected(out, before, tracker, "on track T002")
    swap = commands.relabel(tracker, 0, "T001", "T002", exchange=True)
    assert swap.ok
    assert (tracker.tracks["T001"].label, tracker.tracks["T002"].label) == ("T002", "T001")
    assert swap.events == [
        (
            "track.relabel",
            {"track": "T001", "label": "T002", "previous": "T001", "exchanged_with": "T002"},
        )
    ]
    assert swap.effects == (("relabel", "T001", "T002"), ("relabel", "T002", "T001"))
    assert_event_types(swap)


def test_exchange_with_a_free_name_is_a_plain_rename() -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed")
    out = commands.relabel(tracker, 0, "T001", "FREE", exchange=True)
    assert out.ok and out.effects == (("relabel", "T001", "FREE"),)
    assert "exchanged_with" not in out.events[0][1]


def test_a_relabel_is_undone_only_by_another_logged_command() -> None:
    tracker = bare_tracker(T001="confirmed")
    start = snapshot(tracker)
    commands.apply(tracker, 1, "track-relabel", {"track": "T001", "label": "ALPHA"})
    assert snapshot(tracker) != start
    assert "track-undo" not in ACTIONS
    undo = commands.apply(tracker, 2, "track-undo", {})
    assert not undo.ok and "unknown track command" in (undo.reason or "")
    commands.apply(tracker, 3, "track-relabel", {"track": "T001", "label": "T001"})
    assert snapshot(tracker) == start


# ---------------------------------------------------------------------------- merge


def test_merge_folds_the_higher_id_into_the_lower_and_unites_what_they_know() -> None:
    tracker = bare_tracker(T001="confirmed", T002="coasting")
    keep, gone = tracker.tracks["T001"], tracker.tracks["T002"]
    keep.votes, gone.votes = {"rotary-small": 3}, {"rotary-small": 2, "bird": 1}
    keep.sensors, gone.sensors = ["radar-1"], ["eo-1", "radar-1"]
    keep.data_status = gone.data_status = DATA_VERIFIED
    x, p = keep.x[:], [row[:] for row in keep.p]
    out = commands.merge(tracker, 7, ["T002", "T001"])
    assert out.ok
    assert out.events == [("track.merge", {"survivor": "T001", "absorbed": "T002"})]
    assert out.effects == (("merge", "T001", "T002"),)
    assert list(tracker.tracks) == ["T001"]
    assert tracker.graveyard["T002"] == {"tick": 7, "reason": "merged", "merged_into": "T001"}
    assert keep.votes == {"rotary-small": 5, "bird": 1}
    assert keep.sensors == ["eo-1", "radar-1"]
    assert (keep.x, keep.p) == (x, p)  # the survivor's filter is untouched
    assert keep.data_status == DATA_VERIFIED
    assert_event_types(out)


def test_merging_reference_data_into_a_verified_track_taints_it() -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed")
    tracker.tracks["T001"].data_status = DATA_VERIFIED
    tracker.tracks["T002"].data_status = DATA_REFERENCE
    commands.merge(tracker, 0, ("T001", "T002"))
    assert tracker.tracks["T001"].data_status == DATA_REFERENCE


def test_the_lower_id_counts_numerically() -> None:
    tracker = bare_tracker(T999="confirmed", T1000="confirmed")
    out = commands.merge(tracker, 0, ["T1000", "T999"])
    assert out.effects == (("merge", "T999", "T1000"),)


@pytest.mark.parametrize(
    ("tracks", "text"),
    [
        (["T001"], "exactly two"),
        (["T001", "T001"], "exactly two"),
        (["T001", "T002", "T003"], "exactly two"),
        (["T001", "T404"], "no live track 'T404'"),
        (["T001", "T003"], "tentative"),
    ],
)
def test_merge_refuses_what_it_cannot_do(tracks: list[str], text: str) -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed", T003="tentative")
    before = snapshot(tracker)
    assert_rejected(commands.merge(tracker, 0, tracks), before, tracker, text)


# ---------------------------------------------------------------------------- split


def test_split_clones_a_confirmed_track_and_the_copy_is_independent() -> None:
    tracker = bare_tracker(T001="confirmed")
    source = tracker.tracks["T001"]
    out = commands.split(tracker, 40, "T001")
    assert out.ok
    assert out.events == [("track.split", {"source": "T001", "new": "T002"})]
    assert out.effects == (("split", "T001", "T002"),)
    clone = tracker.tracks["T002"]
    assert (clone.status, clone.born, clone.label) == ("confirmed", 40, "T002")
    assert (clone.x, clone.p) == (source.x, source.p)
    clone.x[0] += 10.0
    assert source.x[0] == 0.0 and list(tracker.tracks) == ["T001", "T002"]
    assert_event_types(out)


def test_a_coasting_track_is_cloned_as_confirmed_and_a_tentative_one_stays_tentative() -> None:
    tracker = bare_tracker(T001="coasting", T002="tentative")
    commands.split(tracker, 5, "T001")
    commands.split(tracker, 5, "T002")
    assert tracker.tracks["T003"].status == "confirmed"
    assert tracker.tracks["T004"].status == "tentative"


def test_split_refuses_an_unknown_track() -> None:
    tracker = bare_tracker(T001="confirmed")
    before = snapshot(tracker)
    assert_rejected(commands.split(tracker, 0, "T404"), before, tracker, "no live track")


# ---------------------------------------------------------------------------- drop


def test_drop_removes_a_track_with_reason_operator() -> None:
    tracker = bare_tracker(T001="confirmed", T002="tentative")
    out = commands.drop(tracker, 12, "T002")
    assert out.ok and out.effects == (("drop", "T002"),)
    assert out.events[0][0] == "track.drop"
    assert out.events[0][1]["reason"] == "operator" and out.events[0][1]["track"] == "T002"
    assert tracker.graveyard["T002"]["reason"] == "operator" and "T002" not in tracker.tracks
    assert_event_types(out)
    before = snapshot(tracker)
    assert_rejected(commands.drop(tracker, 13, "T002"), before, tracker, "no live track")


# ---------------------------------------------------------------------------- the action records


def test_apply_runs_the_four_actions() -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed", T003="confirmed")
    assert commands.apply(tracker, 1, "track-relabel", {"track": "T001", "label": "A"}).ok
    assert commands.apply(
        tracker, 1, "track-relabel", {"track": "T002", "label": "A", "exchange": True}
    ).ok
    assert [t.label for t in tracker.tracks.values()] == ["T002", "A", "T003"]
    assert commands.apply(tracker, 2, "track-split", {"track": "T003"}).ok
    assert commands.apply(tracker, 3, "track-merge", {"tracks": ("T003", "T004")}).ok
    assert commands.apply(tracker, 4, "track-drop", {"track": "T002"}).ok
    assert list(tracker.tracks) == ["T001", "T003"]
    assert ACTIONS == ("track-relabel", "track-merge", "track-split", "track-drop")


@pytest.mark.parametrize(
    ("action", "payload", "text"),
    [
        ("track-fly", {}, "unknown track command"),
        ("track-relabel", "T001", "must be an object"),
        ("track-relabel", {"track": "T001", "label": "X", "colour": "red"}, "unexpected field"),
        ("track-relabel", {"track": 1, "label": "X"}, "needs track"),
        ("track-relabel", {"track": "T001"}, "needs track"),
        ("track-relabel", {"track": "T001", "label": 5}, "needs track"),
        ("track-relabel", {"track": "T001", "label": "X", "exchange": "yes"}, "needs track"),
        ("track-relabel", {"track": "T404", "label": "X"}, "no live track"),
        ("track-merge", {"tracks": "T001"}, "list of two"),
        ("track-merge", {"tracks": [1, 2]}, "list of two"),
        ("track-merge", {}, "list of two"),
        ("track-merge", {"tracks": ["T001", "T002"], "track": "T001"}, "unexpected field"),
        ("track-merge", {"tracks": ["T001", "T404"]}, "no live track"),
        ("track-split", {}, "needs track"),
        ("track-split", {"track": None}, "needs track"),
        ("track-drop", {"track": ["T001"]}, "needs track"),
        ("track-drop", {"track": "T404"}, "no live track"),
    ],
)
def test_apply_rejects_bad_payloads_without_touching_the_tracker(
    action: str, payload: Any, text: str
) -> None:
    tracker = bare_tracker(T001="confirmed", T002="confirmed")
    before = snapshot(tracker)
    assert_rejected(commands.apply(tracker, 0, action, payload), before, tracker, text)


# ---------------------------------------------------------------------------- with the ledger


def test_exchanging_the_labels_of_the_documented_swap_restores_the_picture() -> None:
    run = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    tracker, ledger = run.rig.tracker, run.ledger
    tick = run.rig.world.tick
    assert [e["kind"] for e in ledger.open_errors()] == ["swap"]
    assert not ledger.consistent("T001") and not ledger.consistent("T002")

    # Taking the other track's name without an exchange is refused, and nothing moves.
    before = snapshot(tracker)
    refused = commands.apply(tracker, tick, "track-relabel", {"track": "T001", "label": "T002"})
    assert_rejected(refused, before, tracker, "on track T002")
    assert [e["kind"] for e in ledger.open_errors()] == ["swap"]

    fix = commands.apply(
        tracker, tick, "track-relabel", {"track": "T001", "label": "T002", "exchange": True}
    )
    assert fix.ok
    findings = ledger.on_effects(tick, fix.effects)
    assert [e.kind for e in findings] == ["restored"]
    assert findings[0].payload["error_kind"] == "swap" and findings[0].payload["tracks"] == [
        "T001",
        "T002",
    ]
    assert (tracker.tracks["T001"].label, tracker.tracks["T002"].label) == ("T002", "T001")
    assert ledger.consistent("T001") and ledger.consistent("T002")
    assert (ledger.label_of("T001"), ledger.label_of("T002")) == ("T002", "T001")
    assert ledger.open_errors() == []

    # The drones fly on and the picture stays right.
    run.run_to(900)
    assert ledger.open_errors() == [] and ledger.consistent("T001") and ledger.consistent("T002")
    assert [k for _, k in run.kinds()].count("swap") == 2  # the original pair, nothing new


def test_fixing_only_one_of_the_two_tracks_leaves_the_swap_open() -> None:
    run = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    tick = run.rig.world.tick
    # T001 takes a spare name; T002 is still wrong, so the swap is still open.
    spare = commands.apply(
        run.rig.tracker, tick, "track-relabel", {"track": "T002", "label": "SPARE"}
    )
    assert run.ledger.on_effects(tick, spare.effects) == []
    assert [e["kind"] for e in run.ledger.open_errors()] == ["swap"]
    assert not run.ledger.consistent("T002")


def test_an_operator_split_is_not_counted_as_a_tracker_split() -> None:
    run = crossing(SWAP_SEED, ticks=300)
    tick = run.rig.world.tick
    out = commands.apply(run.rig.tracker, tick, "track-split", {"track": "T001"})
    assert out.ok and run.ledger.on_effects(tick, out.effects) == []
    run.run_to(700)
    assert "split" not in [k for _, k in run.kinds()]


def test_bare_tracks_are_built_with_an_independent_covariance() -> None:
    a, b = bare_track("T001"), bare_track("T002")
    a.p[0][0] = 1.0
    assert b.p[0][0] == 400.0
