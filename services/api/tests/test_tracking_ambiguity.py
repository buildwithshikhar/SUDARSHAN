"""The association-error policy: structure, probabilities and seeded behaviour with real tracks."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sim.sensors import Detection
from sim.tracking import Component, NominalPolicy, Pair, Resolution, Tracker
from sim.tracking.ambiguity import MAX_SWAP_SIDE, ErrorModel, ErrorPolicy
from sim.tracking.associate import check, components

from .tracking_cases import (
    RADAR,
    SWAP_SEED,
    SWAP_TICK,
    component,
    crossing,
    crossing_threats,
    formation_threats,
    parallel_threats,
)
from .tracking_rig import Rig, radar_params, scenario, sensor

API_DIR = Path(__file__).resolve().parents[1]
DRAWS = [0.0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 0.9, 0.999999]


# ---------------------------------------------------------------------------- the model


def test_the_defaults_are_the_documented_ones_and_serialise() -> None:
    model = ErrorModel()
    assert model.to_state() == {
        "swap_max": 0.5,
        "swap_scale": 4.0,
        "split_max": 0.15,
        "merge_max": 0.15,
        "clutter_gain": 0.5,
    }
    assert ErrorPolicy().model == model


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"swap_max": -0.1}, "swap_max is a probability"),
        ({"split_max": 1.5}, "split_max is a probability"),
        ({"merge_max": 2.0}, "merge_max is a probability"),
        ({"swap_scale": 0.0}, "swap_scale must be positive"),
        ({"clutter_gain": -1.0}, "clutter_gain cannot be negative"),
        ({"swap_max": 0.6, "split_max": 0.3, "merge_max": 0.2}, "sum to 1 or less"),
    ],
)
def test_a_model_that_is_not_a_set_of_probabilities_is_refused(
    change: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ErrorModel(**change)


# ---------------------------------------------------------------------------- structure

#: Two tracks, two reports, one clearly best assignment and one plausible swap.
CROSS = (("A", 0, 1.0), ("B", 1, 1.5), ("A", 1, 3.0), ("B", 0, 3.5))
#: The same plus a third report in track A's gate.
CROWDED = (*CROSS, ("A", 2, 2.0))


def test_an_unambiguous_component_offers_no_error_at_any_draw() -> None:
    comp = component(("A", 0, 2.0))
    policy = ErrorPolicy()
    assert not comp.ambiguous
    assert policy.options(comp) == []
    for draw in DRAWS:
        assert policy.resolve(comp, draw) == Resolution("nominal", (("A", 0),))


def test_modes_that_do_not_apply_take_no_interval() -> None:
    policy = ErrorPolicy()
    # Two tracks, one report: nothing to swap, nothing left over, one pair to merge.
    one_report = component(("A", 0, 1.0), ("B", 0, 2.0))
    assert policy.options(one_report) == []
    # One track, two reports: only a split can happen, and it has the whole interval.
    one_track = component(("A", 0, 1.0), ("A", 1, 2.0))
    (option,) = policy.options(one_track)
    assert option.mode == "split"
    assert option.probability == pytest.approx(0.15 * (1.0 - math.exp(-0.5)))
    assert policy.resolve(one_track, 0.0) == Resolution("split", (("A", 0),), spawn=(1,))
    assert policy.resolve(one_track, option.probability) == Resolution("nominal", (("A", 0),))
    # Only the diagonal pairs and one cross pair are gated: no complete alternative exists.
    no_alternative = component(("A", 0, 1.0), ("B", 1, 1.5), ("A", 1, 3.0))
    assert [o.mode for o in policy.options(no_alternative)] == ["merge"]


def test_the_swap_chance_falls_with_the_cost_of_the_alternative() -> None:
    policy = ErrorPolicy()
    swap, merge = policy.options(component(*CROSS))
    assert (swap.mode, merge.mode) == ("swap", "merge")
    # Nominal A0 + B1 costs 2.5, the alternative A1 + B0 costs 6.5.
    assert swap.probability == pytest.approx(0.5 * math.exp(-(6.5 - 2.5) / 4.0))
    assert swap.resolution == Resolution("swap", (("A", 1), ("B", 0)))
    # The pair dropped by a merge is the dearest nominal one, B1.
    assert merge.probability == pytest.approx(0.15 * math.exp(-1.5 / 4.0))
    assert merge.resolution == Resolution("merge", (("A", 0),))
    cheaper = policy.options(component(("A", 0, 1.0), ("B", 1, 1.5), ("A", 1, 1.5), ("B", 0, 1.5)))
    assert cheaper[0].probability > swap.probability


def test_a_dearer_alternative_never_beats_the_nominal_and_a_cheaper_one_is_capped() -> None:
    # The greedy nominal is not the cheapest assignment here; the swap then costs nothing extra.
    comp = component(("A", 0, 1.0), ("B", 1, 9.0), ("A", 1, 1.5), ("B", 0, 1.6))
    swap = ErrorPolicy().options(comp)[0]
    assert swap.mode == "swap"
    assert swap.probability == pytest.approx(0.5)


def test_the_unit_interval_is_cut_swap_then_split_then_merge_then_nominal() -> None:
    comp = component(*CROWDED)
    policy = ErrorPolicy()
    swap, split, merge = policy.options(comp)
    assert (swap.mode, split.mode, merge.mode) == ("swap", "split", "merge")
    # The cheapest alternative takes the report that was left over: A2 + B1 = 3.5.
    assert swap.probability == pytest.approx(0.5 * math.exp(-(3.5 - 2.5) / 4.0))
    assert swap.resolution == Resolution("swap", (("A", 2), ("B", 1)))
    assert split.probability == pytest.approx(0.15 * (1.0 - math.exp(-0.5)))
    assert split.resolution == Resolution("split", (("A", 0), ("B", 1)), spawn=(2,))
    assert merge.resolution == Resolution("merge", (("A", 0),))
    edges = [
        swap.probability,
        swap.probability + split.probability,
        swap.probability + split.probability + merge.probability,
    ]
    nominal = Resolution("nominal", (("A", 0), ("B", 1)))
    assert policy.resolve(comp, 0.0) == swap.resolution
    assert policy.resolve(comp, edges[0] - 1e-9) == swap.resolution
    assert policy.resolve(comp, edges[0]) == split.resolution
    assert policy.resolve(comp, edges[1] - 1e-9) == split.resolution
    assert policy.resolve(comp, edges[1]) == merge.resolution
    assert policy.resolve(comp, edges[2] - 1e-9) == merge.resolution
    assert policy.resolve(comp, edges[2]) == nominal
    assert policy.resolve(comp, 0.999999) == nominal


def test_more_plots_in_the_gate_mean_more_splits() -> None:
    policy = ErrorPolicy()
    one = policy.options(component(("A", 0, 1.0), ("A", 1, 2.0)))[0]
    three = policy.options(component(("A", 0, 1.0), ("A", 1, 2.0), ("A", 2, 3.0), ("A", 3, 4.0)))[0]
    assert three.probability > one.probability
    assert three.resolution.spawn == (1,)  # the leftover plot with the best fit


def test_a_merge_drops_the_dearer_pair_and_ties_go_to_the_larger_track_id() -> None:
    tied = component(("A", 0, 2.0), ("B", 1, 2.0), ("A", 1, 5.0), ("B", 0, 6.0))
    merge = [o for o in ErrorPolicy().options(tied) if o.mode == "merge"][0]
    assert merge.resolution == Resolution("merge", (("A", 0),))


def test_a_model_with_a_zero_maximum_never_offers_that_mode() -> None:
    policy = ErrorPolicy(ErrorModel(swap_max=0.0, split_max=0.0, merge_max=0.0))
    comp = component(*CROWDED)
    assert policy.options(comp) == []
    assert all(policy.resolve(comp, d).mode == "nominal" for d in DRAWS)
    only_split = ErrorPolicy(ErrorModel(swap_max=0.0, merge_max=0.0, split_max=0.5))
    assert [o.mode for o in only_split.options(comp)] == ["split"]


def test_a_very_large_component_is_not_searched_for_swaps() -> None:
    def chain(tracks: int, reports: int) -> Component:
        pairs = [(f"T{i}", i, 1.0) for i in range(tracks)]
        pairs += [(f"T{i}", (i + 1) % reports, 2.0) for i in range(tracks)]
        return component(*pairs)

    policy = ErrorPolicy()
    assert MAX_SWAP_SIDE == 8
    too_many_tracks = chain(9, 10)
    too_many_reports = component(*[("T0", j, 1.0 + j) for j in range(9)], ("T1", 0, 5.0))
    assert len(too_many_tracks.tracks) == 9 and len(too_many_reports.measurements) == 9
    assert "swap" not in [o.mode for o in policy.options(too_many_tracks)]
    assert "swap" not in [o.mode for o in policy.options(too_many_reports)]
    ring = chain(8, 8)
    swap = [o for o in policy.options(ring) if o.mode == "swap"][0]
    # The only cheaper-than-nothing alternative shifts every track one report along.
    assert swap.probability == pytest.approx(0.5 * math.exp(-(16.0 - 8.0) / 4.0))
    check(ring, swap.resolution)


# ---------------------------------------------------------------------------- properties


@st.composite
def gated_pairs(draw: st.DrawFn) -> list[Pair]:
    cells = draw(st.sets(st.tuples(st.integers(0, 3), st.integers(0, 4)), min_size=1, max_size=14))
    costs = st.floats(min_value=0.0, max_value=13.0, allow_nan=False)
    return [Pair(f"T{t}", r, draw(costs)) for t, r in sorted(cells)]


@settings(max_examples=150, deadline=None)
@given(pairs=gated_pairs())
def test_every_resolution_the_policy_gives_is_a_valid_reading_of_its_component(
    pairs: list[Pair],
) -> None:
    policy = ErrorPolicy(ErrorModel(swap_max=0.4, split_max=0.3, merge_max=0.3))
    for comp in components("radar-1", pairs):
        options = policy.options(comp)
        assert sum(o.probability for o in options) <= 1.0
        assert all(0.0 < o.probability <= 1.0 for o in options)
        if not comp.ambiguous:
            assert options == []
        for draw in DRAWS:
            resolution = policy.resolve(comp, draw)
            check(comp, resolution)
            used = {i for _, i in resolution.pairs}
            assert not set(resolution.spawn) & used
            if resolution.mode == "nominal":
                assert resolution.pairs == tuple((p.track, p.index) for p in comp.nominal)
            if resolution.mode == "swap":
                assert len(resolution.pairs) == len(comp.nominal)
                assert set(resolution.pairs) != {(p.track, p.index) for p in comp.nominal}
            if resolution.mode == "split":
                assert len(resolution.spawn) == 1 and len(resolution.pairs) == len(comp.nominal)
            if resolution.mode == "merge":
                assert len(resolution.pairs) == len(comp.nominal) - 1
            assert policy.resolve(comp, draw) == resolution  # no hidden state


# ---------------------------------------------------------------------------- seeded, real tracks


class Spy:
    """An `AmbiguityPolicy` that records every component it is asked about and its answer."""

    def __init__(self) -> None:
        self.inner = ErrorPolicy()
        self.asked: list[tuple[Component, Resolution]] = []

    def resolve(self, component: Component, draw: float) -> Resolution:
        answer = self.inner.resolve(component, draw)
        self.asked.append((component, answer))
        return answer


def test_the_documented_swap_is_found_at_the_same_tick_every_time() -> None:
    # Documented swap: seed 47, tick 648. The policy swaps the two tracks' reports at tick 624,
    # and by 648 the last five reports of T001 and T002 point at the other drone.
    first = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    second = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    swaps = [(t, e.payload) for t, e in first.events if e.kind == "swap"]
    assert [t for t, _ in swaps] == [SWAP_TICK, SWAP_TICK]
    assert {p["track"] for _, p in swaps} == {"T001", "T002"}
    assert {(p["from_truth"], p["to_truth"]) for _, p in swaps} == {
        ("alpha", "bravo"),
        ("bravo", "alpha"),
    }
    assert [p["partner"] for _, p in swaps] == ["T002", "T001"]
    assert swaps[0][1]["error_id"] == swaps[1][1]["error_id"]
    assert first.modes()["swap"] == 1
    assert first.kinds() == second.kinds()
    assert json.dumps(first.rig.tracker.state()) == json.dumps(second.rig.tracker.state())
    assert first.ledger.state() == second.ledger.state()


def test_the_swap_belongs_to_the_policy_not_to_noise() -> None:
    nominal = crossing(SWAP_SEED, NominalPolicy(), ticks=900)
    assert [k for _, k in nominal.kinds() if k == "swap"] == []
    assert crossing(SWAP_SEED, ticks=900).kinds()[0] == (SWAP_TICK, "swap")


def test_other_seeds_do_not_swap_at_that_place() -> None:
    for seed in (1, 2, 3, 13):
        run = crossing(seed, ticks=SWAP_TICK + 1)
        assert "swap" not in [k for _, k in run.kinds()]


DETERMINISM_SCRIPT = """
import json
from tests.tracking_cases import SWAP_SEED, SWAP_TICK, crossing
run = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
print(json.dumps([run.kinds(), run.rig.tracker.state(), run.ledger.state()], sort_keys=True))
"""


def test_the_swap_is_the_same_in_two_processes_with_different_hash_salts() -> None:
    here = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    expected = json.dumps(
        [here.kinds(), here.rig.tracker.state(), here.ledger.state()], sort_keys=True
    )
    for salt in ("1", "2"):
        done = subprocess.run(  # noqa: S603 - fixed interpreter and script
            [sys.executable, "-c", DETERMINISM_SCRIPT],
            cwd=API_DIR,
            env=os.environ | {"PYTHONHASHSEED": salt},
            capture_output=True,
            text=True,
            check=True,
        )
        assert done.stdout.strip() == expected


def test_a_seed_repeats_exactly_and_different_seeds_differ() -> None:
    def fingerprint(seed: int) -> str:
        run = crossing(seed, ticks=700)
        return json.dumps([run.kinds(), run.rig.tracker.state()], sort_keys=True)

    assert fingerprint(5) == fingerprint(5)
    assert len({fingerprint(s) for s in (5, 6, 7, 8)}) == 4


def test_targets_that_stay_apart_never_err_whatever_the_seed() -> None:
    # 300 seeds, the drones 1500 m apart in cross-range, no false alarms. The only components
    # the policy is ever asked about hold nothing to get wrong, it answers nominal every time, and
    # the whole run is identical to one with the nominal policy. Seed 4 is the one run in which
    # the tracker itself, on a noisy radar dropout, starts a second track on a drone it still has;
    # the ledger reports that split, which happens without any error policy.
    noise_splits = []
    spec = scenario(parallel_threats(1500.0))
    for seed in range(300):
        spy = Spy()
        run = crossing(seed, spy, spec=spec, ticks=500)
        assert all(answer.mode == "nominal" for _, answer in spy.asked)
        assert all(spy.inner.options(comp) == [] for comp, _ in spy.asked)
        assert set(run.modes()) <= {"nominal"}
        if seed < 25:  # the nominal policy gives the same run (kept to 25 seeds for speed)
            plain = crossing(seed, NominalPolicy(), spec=spec, ticks=500)
            assert json.dumps(run.rig.tracker.state()) == json.dumps(plain.rig.tracker.state())
            assert run.kinds() == plain.kinds()
        kinds = [k for _, k in run.kinds()]
        assert "swap" not in kinds and "merge" not in kinds
        if "split" in kinds:
            noise_splits.append(seed)
    assert noise_splits == [4]


def test_a_close_pair_is_asked_about_and_errs_in_every_mode_when_the_chances_are_raised() -> None:
    # The default maxima make a split or a merge rare. To exercise each mode with real tracks the
    # maxima are raised here; the structure (who can err, when) is the shipped one.
    model = ErrorModel(swap_max=0.3, split_max=0.35, merge_max=0.35)
    seen: dict[str, int] = {}
    for seed in range(1, 7):
        run = crossing(seed, ErrorPolicy(model), threats=formation_threats(12.0), ticks=700)
        for mode, n in run.modes().items():
            seen[mode] = seen.get(mode, 0) + n
    assert set(seen) == {"merge", "nominal", "split", "swap"}


# ---------------------------------------------------------------------------- the tracker never sees truth


def test_a_trainee_view_carries_no_ground_truth() -> None:
    rig = Rig(scenario(crossing_threats()), 3, [sensor("radar-1", radar_params(), RADAR)])
    rig.run_to(100)
    detections: list[Detection] = []
    while not detections:
        detections = rig.suite.detect(rig.world)
        rig.world.step()
    assert detections[0].truth_id is not None
    assert not {"truth_id", "truth"} & set(detections[0].trainee_view())


def test_the_tracker_output_is_the_same_with_the_ledger_and_without_it() -> None:
    def tracker_only(seed: int) -> Tracker:
        rig = Rig(
            scenario(crossing_threats()),
            seed,
            [sensor("radar-1", radar_params(), RADAR)],
            policy=ErrorPolicy(),
        )
        rig.run_to(SWAP_TICK + 1)
        return rig.tracker

    with_ledger = crossing(SWAP_SEED, ticks=SWAP_TICK + 1)
    without = tracker_only(SWAP_SEED)
    assert json.dumps(with_ledger.rig.tracker.state()) == json.dumps(without.state())
    # Scrambling what the ledger is told changes only the ledger.
    scrambled = crossing(SWAP_SEED, ticks=0)
    swap_names = {"alpha": "bravo", "bravo": "alpha", None: None}
    while scrambled.rig.world.tick < SWAP_TICK + 1:
        scrambled.rig.step()
        at, result = scrambled.rig.history[-1]
        told = {r: swap_names[t] for r, t in scrambled.rig.truth.items()}
        scrambled.events += [(at, e) for e in scrambled.ledger.observe(at, result, told)]
    assert json.dumps(scrambled.rig.tracker.state()) == json.dumps(without.state())
    assert scrambled.kinds() == with_ledger.kinds()
    assert scrambled.events[0][1].payload["from_truth"] == "bravo"
    assert with_ledger.events[0][1].payload["from_truth"] == "alpha"
