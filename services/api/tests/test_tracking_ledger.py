"""The truth ledger: identities, swaps, splits, merges and when an error counts as restored."""

import json

import pytest

from sim.tracking import Association, NominalPolicy, TrackEvent, UpdateResult
from sim.tracking.ledger import (
    ERROR_KINDS,
    SPLIT_TICKS,
    TRUTH_EVENT_KINDS,
    LedgerEvent,
    TruthLedger,
)

from .tracking_cases import (
    SWAP_SEED,
    SWAP_TICK,
    Feed,
    confirm,
    crossing,
    drop_event,
    formation_threats,
)


def kinds(events: list[LedgerEvent]) -> list[str]:
    return [e.kind for e in events]


# ---------------------------------------------------------------------------- identity and labels


def test_identity_needs_three_real_reports_and_ties_go_to_the_first_name() -> None:
    f = Feed()
    assert f.ledger.identity_of("T1") is None
    f.step({"T1": ["a", None]})
    f.step({"T1": ["b"]})
    f.step({"T1": [None]})
    assert f.ledger.identity_of("T1") is None  # two real reports in the window
    f.step({"T1": ["a"]})
    assert f.ledger.identity_of("T1") == "a"  # a, None, b, None, a
    f.step({"T1": ["b"]})
    assert f.ledger.identity_of("T1") == "b"  # None, b, None, a, b: false alarms count for nothing
    f.step({"T1": ["a"]})
    assert f.ledger.identity_of("T1") == "a"  # b, None, a, b, a: two each, so the first name


def test_a_tie_in_the_window_goes_to_the_name_that_sorts_first() -> None:
    f = Feed()
    f.step({"T1": ["b", "a", "b", "a", None]})
    assert f.ledger.identity_of("T1") == "a"


def test_a_confirmed_track_binds_its_label_as_soon_as_its_identity_is_known() -> None:
    f = Feed()
    f.step({"T1": ["a"]}, [TrackEvent("init", "T1", 0, {"track": "T1"})])
    f.step({}, [confirm("T1")])
    assert f.ledger.label_of("T1") == "T1"
    assert not f.ledger.consistent("T1")  # confirmed, but nothing known about it yet
    f.run(2, {"T1": ["a"]})
    assert f.ledger.consistent("T1")


def test_relabelling_a_consistent_track_carries_the_binding_but_a_wrong_one_cannot_be_renamed_right() -> (
    None
):
    f = Feed()
    f.start(T1="a", T2="b")
    assert f.ledger.on_relabel(f.tick, "T1", "ALPHA") == []
    assert f.ledger.label_of("T1") == "ALPHA" and f.ledger.consistent("T1")
    f.run(3, {"T1": ["b"]})  # T1 now follows b under a name bound to a
    assert not f.ledger.consistent("T1")
    assert f.ledger.on_relabel(f.tick, "T1", "FRESH") == []
    assert not f.ledger.consistent("T1")  # naming it does not make it right
    assert [e["kind"] for e in f.ledger.open_errors()] == ["swap"]


# ---------------------------------------------------------------------------- swaps


def swapped() -> Feed:
    f = Feed()
    f.start(T1="a", T2="b")
    return f


def test_two_tracks_that_exchange_drones_are_one_swap_with_two_findings() -> None:
    f = swapped()
    assert f.run(2, {"T1": ["b"], "T2": ["a"]}) == []  # not yet: the window still says a and b
    first, second = f.step({"T1": ["b"], "T2": ["a"]})
    assert (first.kind, second.kind) == ("swap", "swap")
    assert first.payload == {
        "error_id": 1,
        "from_truth": "a",
        "partner": "T2",
        "tick": f.tick - 1,
        "to_truth": "b",
        "track": "T1",
    }
    assert second.payload["partner"] == "T1" and second.payload["error_id"] == 1
    assert (second.payload["from_truth"], second.payload["to_truth"]) == ("b", "a")
    (error,) = f.ledger.open_errors()
    assert (error["id"], error["kind"], error["tracks"], error["truths"]) == (
        1,
        "swap",
        ["T1", "T2"],
        ["a", "b"],
    )
    assert error["open"] and error["restored_tick"] is None
    assert not f.ledger.consistent("T1") and not f.ledger.consistent("T2")


def test_a_partner_that_changes_a_tick_later_joins_the_same_error() -> None:
    f = swapped()
    f.step({"T1": ["b"], "T2": ["b"]})
    f.step({"T1": ["b"], "T2": ["a"]})
    (alone,) = f.step({"T1": ["b"], "T2": ["a"]})
    assert alone.payload["track"] == "T1" and alone.payload["partner"] is None
    (joined,) = f.step({"T2": ["a"]})
    assert joined.payload["track"] == "T2" and joined.payload["partner"] == "T1"
    assert joined.payload["error_id"] == alone.payload["error_id"] == 1
    assert [e["tracks"] for e in f.ledger.open_errors()] == [["T1", "T2"]]


def test_a_change_three_ticks_later_is_a_different_error() -> None:
    f = swapped()
    f.run(3, {"T1": ["b"]})
    f.run(3, {"T2": ["a"]})
    assert [e["id"] for e in f.ledger.open_errors()] == [1, 2]
    assert [e["tracks"] for e in f.ledger.open_errors()] == [["T1"], ["T2"]]


def test_a_partner_whose_error_is_already_restored_does_not_pull_the_new_change_in() -> None:
    f = swapped()
    f.step({"T1": ["b"]})
    f.step({"T1": ["b"], "T2": ["a"]})
    (alone,) = f.step({"T1": ["b"], "T2": ["a"]})
    assert alone.payload["partner"] is None  # T2 has not changed yet
    restored = f.ledger.on_relabel(f.tick, "T1", "T2")  # T1 takes the name bound to b
    assert [e.kind for e in restored] == ["restored"] and restored[0].payload["tracks"] == ["T1"]
    (later,) = f.step({"T2": ["a"]})
    assert later.payload["partner"] == "T1" and later.payload["error_id"] == 2


def test_a_track_that_is_not_confirmed_cannot_be_swapped() -> None:
    f = Feed()
    f.step({"T1": ["a"]}, [TrackEvent("init", "T1", 0, {"track": "T1"})])
    f.run(5, {"T1": ["a"]})
    assert f.run(5, {"T1": ["b"]}) == []
    assert f.ledger.identity_of("T1") == "b" and f.ledger.open_errors() == []


def test_a_swap_that_reverts_is_restored() -> None:
    f = swapped()
    f.run(3, {"T1": ["b"]})
    assert [e["kind"] for e in f.ledger.open_errors()] == ["swap"]
    assert f.run(2, {"T1": ["a"]}) == []
    out = f.step({"T1": ["a"]})
    assert kinds(out) == ["restored"]  # back on a, the drone its label stands for: no new error
    assert f.ledger.consistent("T1") and f.ledger.open_errors() == []


def test_exchanging_the_labels_of_a_swapped_pair_restores_it() -> None:
    f = swapped()
    f.run(3, {"T1": ["b"], "T2": ["a"]})
    assert len(f.ledger.open_errors()) == 1
    # The first relabel alone does not restore it: T2 still wears the wrong name.
    assert f.ledger.on_effects(f.tick, [("relabel", "T1", "T2")]) == []
    (done,) = f.ledger.on_effects(f.tick, [("relabel", "T2", "T1")])
    assert done.kind == "restored"
    assert done.payload == {
        "error_id": 1,
        "error_kind": "swap",
        "tick": f.tick,
        "tracks": ["T1", "T2"],
        "truths": ["a", "b"],
    }
    assert f.ledger.open_errors() == []
    assert f.ledger.consistent("T1") and f.ledger.consistent("T2")
    assert f.ledger.errors()[0]["restored_tick"] == f.tick


def test_dropping_the_tracks_of_a_swap_ends_it() -> None:
    f = swapped()
    f.run(3, {"T1": ["b"], "T2": ["a"]})
    assert f.ledger.on_drop(f.tick, "T1") == []
    assert f.step({}, [drop_event("T2")])[0].kind == "restored"
    assert f.ledger.open_errors() == []


# ---------------------------------------------------------------------------- splits


def test_two_confirmed_tracks_on_one_drone_for_forty_ticks_are_one_split() -> None:
    f = Feed()
    f.start(T1="a", T2="a")
    first = f.tick - 1  # both tracks are confirmed, and both follow a, from this tick on
    out = f.run(60, {"T1": ["a"], "T2": ["a"]})
    assert kinds(out) == ["split"]
    assert out[0].payload == {
        "error_id": 1,
        "tick": first + SPLIT_TICKS - 1,
        "tracks": ["T1", "T2"],
        "truth": "a",
    }
    assert f.run(100, {"T1": ["a"], "T2": ["a"]}) == []  # once per episode
    assert [e["kind"] for e in f.ledger.open_errors()] == ["split"]


def test_a_gap_in_the_ticks_restarts_the_count() -> None:
    f = Feed()
    f.start(T1="a", T2="a")
    f.run(10, {"T1": ["a"], "T2": ["a"]})
    f.tick += 5  # the ledger was not told about these ticks
    resumed = f.tick
    out = f.run(60, {"T1": ["a"], "T2": ["a"]})
    assert out[0].payload["tick"] == resumed + SPLIT_TICKS - 1


def test_folding_the_duplicate_restores_the_split_and_a_new_one_is_a_new_error() -> None:
    f = Feed()
    f.start(T1="a", T2="a")
    f.run(50, {"T1": ["a"], "T2": ["a"]})
    out = f.step({"T1": ["a"]}, [drop_event("T2", "duplicate", "T1")])
    assert kinds(out) == ["restored"] and out[0].payload["error_kind"] == "split"
    assert f.ledger.open_errors() == []
    f.start(T3="a")
    again = f.run(60, {"T1": ["a"], "T3": ["a"]})
    assert kinds(again) == ["split"] and again[0].payload["error_id"] == 2


def test_operator_commands_restore_a_split_and_their_own_copies_are_not_tracker_splits() -> None:
    f = Feed()
    f.start(T1="a", T2="a")
    f.run(50, {"T1": ["a"], "T2": ["a"]})
    (done,) = f.ledger.on_merge(f.tick, "T1", "T2")
    assert done.kind == "restored"

    g = Feed()
    g.start(T1="a")
    assert g.ledger.on_split(g.tick, "T1", "T9") == []
    assert g.run(120, {"T1": ["a"], "T9": ["a"]}) == []
    assert g.ledger.open_errors() == []


def test_splitting_a_track_the_ledger_has_not_seen_is_harmless() -> None:
    ledger = TruthLedger()
    assert ledger.on_split(0, "X", "Y") == []
    assert ledger.identity_of("Y") is None


# ---------------------------------------------------------------------------- merges


def test_two_drones_folded_into_one_track_are_a_merge_until_each_has_a_track_again() -> None:
    f = Feed()
    f.start(T1="a", T2="b")
    (found,) = f.step({"T1": ["a"]}, [drop_event("T2", "duplicate", "T1")])
    assert found.kind == "merge"
    assert found.payload == {
        "dropped": "T2",
        "error_id": 1,
        "survivor": "T1",
        "tick": f.tick - 1,
        "truth_dropped": "b",
        "truth_survivor": "a",
    }
    assert f.run(5, {"T1": ["a"]}) == []
    f.start(T3="b")
    (error,) = f.ledger.errors()
    assert not error["open"]
    assert error["tracks"] == ["T1", "T2"] and error["truths"] == ["a", "b"]


def test_the_restoration_is_reported_when_the_second_drone_gets_its_track() -> None:
    f = Feed()
    f.start(T1="a", T2="b")
    f.step({"T1": ["a"]}, [drop_event("T2", "merged-error", "T1")])
    f.step({"T3": ["b"]}, [TrackEvent("init", "T3", f.tick, {"track": "T3"})])
    f.run(3, {"T3": ["b"], "T1": ["a"]})
    out = f.step({}, [confirm("T3")])
    assert kinds(out) == ["restored"] and out[0].payload["error_kind"] == "merge"


@pytest.mark.parametrize(
    ("reason", "into", "setup"),
    [
        ("lost", "T1", {"T1": "a", "T2": "b"}),
        ("duplicate", None, {"T1": "a", "T2": "b"}),
        ("duplicate", "T1", {"T1": "a", "T2": "a"}),
        ("merged", "T1", {"T1": "a", "T2": "b"}),
    ],
)
def test_other_drops_are_not_merge_errors(
    reason: str, into: str | None, setup: dict[str, str]
) -> None:
    f = Feed()
    f.start(**setup)
    assert f.step({}, [drop_event("T2", reason, into)]) == []
    assert f.ledger.errors() == []


def test_a_duplicate_with_an_unknown_identity_is_not_a_merge_error() -> None:
    f = Feed()
    f.step({"T1": ["a"]}, [TrackEvent("init", "T1", 0, {"track": "T1"})])
    f.run(4, {"T1": ["a"], "T2": [None]})
    f.step({}, [confirm("T1")])
    assert f.step({}, [drop_event("T2", "duplicate", "T1")]) == []  # T2 never had an identity
    f.run(1, {"T3": ["b"]})
    assert f.step({}, [drop_event("T1", "duplicate", "T3")]) == []  # T3 has too few reports


def test_the_operator_merging_two_tracks_is_not_a_tracker_error() -> None:
    f = Feed()
    f.start(T1="a", T2="b")
    assert f.ledger.on_merge(f.tick, "T1", "T2") == []
    assert f.ledger.errors() == []


# ---------------------------------------------------------------------------- hooks, state, inputs


def test_command_effects_are_passed_on_in_order_and_an_unknown_one_is_refused() -> None:
    f = Feed()
    f.start(T1="a", T2="a")
    f.run(50, {"T1": ["a"], "T2": ["a"]})
    out = f.ledger.on_effects(
        f.tick,
        [("relabel", "T1", "ALPHA"), ("split", "T1", "T9"), ("drop", "T2"), ("merge", "T1", "T9")],
    )
    assert kinds(out) == ["restored"]
    assert f.ledger.label_of("T1") == "ALPHA"
    with pytest.raises(ValueError, match="unknown command effect"):
        f.ledger.on_effects(f.tick, [("teleport", "T1")])


def test_a_report_with_no_ground_truth_is_refused() -> None:
    result = UpdateResult(associations=[Association("T1", 0, "radar-1")])
    with pytest.raises(ValueError, match="no ground truth for report 0"):
        TruthLedger().observe(0, result, {})


def test_the_state_is_sorted_json_and_a_restored_ledger_continues_exactly() -> None:
    a = Feed()
    a.start(T1="a", T2="b")
    a.run(3, {"T1": ["b"], "T2": ["a"]})
    a.ledger.on_relabel(a.tick, "T2", "KILO")
    a.ledger.on_split(a.tick, "T1", "T9")
    a.start(T3="c", T4="c")
    a.run(45, {"T3": ["c"], "T4": ["c"]})
    state = a.ledger.state()
    assert json.dumps(state) == json.dumps(state, sort_keys=True)
    assert json.loads(json.dumps(state)) == state

    b = Feed()
    b.ledger.restore(json.loads(json.dumps(state)))
    b.truth, b.tick, b._ref = dict(a.truth), a.tick, a._ref
    assert b.ledger.state() == state

    def suffix(f: Feed) -> list[LedgerEvent]:
        out = f.step({"T4": ["c"]}, [drop_event("T3", "duplicate", "T4")])
        out += f.ledger.on_effects(f.tick, [("relabel", "T1", "T2"), ("relabel", "T2", "T1")])
        out += f.run(4, {"T1": ["a"], "T2": ["b"]})
        return out

    assert suffix(a) == suffix(b)
    assert a.ledger.state() == b.ledger.state()
    assert [e["id"] for e in a.ledger.open_errors()] == [e["id"] for e in b.ledger.open_errors()]


def test_the_constants_name_the_kinds_the_picture_must_filter() -> None:
    assert ERROR_KINDS == ("swap", "split", "merge")
    assert set(TRUTH_EVENT_KINDS) == {*ERROR_KINDS, "restored"}


# ---------------------------------------------------------------------------- real tracks


def test_an_unfixed_swap_stays_open_while_the_drones_fly_on() -> None:
    run = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    (error,) = run.ledger.open_errors()
    assert error["kind"] == "swap" and error["tick"] == SWAP_TICK
    assert error["tracks"] == ["T001", "T002"] and error["truths"] == ["alpha", "bravo"]
    run.run_to(900)
    (still,) = run.ledger.open_errors()
    assert still["id"] == error["id"]
    assert "restored" not in [k for _, k in run.kinds()]
    assert not run.ledger.consistent("T001") and not run.ledger.consistent("T002")
    assert run.ledger.identity_of("T001") == "bravo" and run.ledger.identity_of("T002") == "alpha"


def test_two_drones_flying_side_by_side_are_folded_into_one_track() -> None:
    # Seed 6, twelve metres apart, nominal tracker: the tracker's own duplicate rule folds the
    # two tracks into one, which for two real drones is a merge error.
    run = crossing(6, NominalPolicy(), threats=formation_threats(12.0), ticks=700)
    merges = [(t, e.payload) for t, e in run.events if e.kind == "merge"]
    assert [t for t, _ in merges] == [131]
    payload = merges[0][1]
    assert {payload["truth_dropped"], payload["truth_survivor"]} == {"alpha", "bravo"}
    assert run.rig.tracker.graveyard[payload["dropped"]]["reason"] == "duplicate"


def test_every_finding_from_real_runs_is_a_plain_json_truth_event() -> None:
    seen = set()
    for seed in (1, 2, 11, 18):
        run = crossing(seed, NominalPolicy(), threats=formation_threats(12.0), ticks=700)
        for _, e in run.events:
            seen.add(e.kind)
            assert e.kind in TRUTH_EVENT_KINDS
            assert json.loads(json.dumps(e.payload)) == e.payload
    assert {"merge", "restored"} <= seen
