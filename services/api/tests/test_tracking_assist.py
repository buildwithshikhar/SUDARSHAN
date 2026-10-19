"""Simulated AI assist: configured rates, keyed draws, reproducibility, due logic, no truth leak."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sim.tracking.assist import (
    NON_THREAT_CLASSES,
    AiAssist,
    Assessment,
    AssistConfig,
    TruthRef,
    is_threat,
    keyed_uniform,
)

API_DIR = Path(__file__).resolve().parent.parent
TICKS_PER_ASSESSMENT = 100  # reassess_s 5.0 at 20 Hz
SEED = 20260101

DRONE = TruthRef("rotary-small")
FIXED_WING = TruthRef("fixed-wing-small")
BIRD = TruthRef("bird")
FALSE_TRACK = TruthRef(None)

LEAK_KEYS = {"true_class", "correct_flag", "truth"}


def five_sigma(p: float, n: int) -> float:
    """Tolerance for an empirical rate: 5 binomial standard errors, 5 * sqrt(p (1 - p) / n).

    At p = 0.9 and n = 40000 the standard error is 0.0015, so the tolerance is 0.0075. The seed is
    fixed, so a pass is reproducible; 5 sigma keeps the test meaningful (a rate wrong by 0.01
    fails) without being tuned to the seed.
    """
    return 5.0 * math.sqrt(p * (1.0 - p) / n)


def confirmed(track_id: str, **extra: Any) -> dict[str, Any]:
    return {"id": track_id, "status": "confirmed", "data_status": "reference", **extra}


def run_trials(
    assist: AiAssist, truth: TruthRef, tracks: int = 10000, epochs: int = 4, prefix: str = "t"
) -> list[Assessment]:
    """tracks x epochs independent (track, epoch) pairs, each assessed exactly once."""
    out: list[Assessment] = []
    for epoch in range(epochs):
        for i in range(tracks):
            got = assist.assess(confirmed(f"{prefix}{i}"), truth, epoch * TICKS_PER_ASSESSMENT)
            assert got is not None
            out.append(got)
    return out


def rate(hits: int, n: int) -> float:
    return hits / n


# --- configured rates ---------------------------------------------------------------------

ALT = AssistConfig(hit_rate=0.6, false_alarm_rate=0.3)
CONFIGS = {"default": AssistConfig(), "alternative": ALT}


@pytest.fixture(scope="module", params=sorted(CONFIGS))
def trials(request: pytest.FixtureRequest) -> dict[str, Any]:
    config = CONFIGS[request.param]
    assist = AiAssist(SEED, config)
    return {
        "config": config,
        "threat": run_trials(assist, DRONE, prefix="d"),
        "bird": run_trials(assist, BIRD, prefix="b"),
        "false": run_trials(assist, FALSE_TRACK, prefix="f"),
    }


def test_hit_rate_matches_the_configured_value(trials: dict[str, Any]) -> None:
    config: AssistConfig = trials["config"]
    got = trials["threat"]
    assert len(got) == 40000
    measured = rate(sum(a.threat for a in got), len(got))
    assert abs(measured - config.hit_rate) < five_sigma(config.hit_rate, len(got))


@pytest.mark.parametrize("kind", ["bird", "false"])
def test_false_alarm_rate_matches_the_configured_value(trials: dict[str, Any], kind: str) -> None:
    config: AssistConfig = trials["config"]
    got = trials[kind]
    assert len(got) == 40000
    measured = rate(sum(a.threat for a in got), len(got))
    assert abs(measured - config.false_alarm_rate) < five_sigma(config.false_alarm_rate, len(got))


def test_class_accuracy_matches_the_configured_value(trials: dict[str, Any]) -> None:
    config: AssistConfig = trials["config"]
    for kind, correct in (("threat", "rotary-small"), ("bird", "bird"), ("false", "unknown")):
        got = trials[kind]
        measured = rate(sum(a.proposed_class == correct for a in got), len(got))
        assert abs(measured - config.class_accuracy) < five_sigma(config.class_accuracy, len(got))


def test_a_wrong_class_is_drawn_evenly_from_the_other_labels(trials: dict[str, Any]) -> None:
    got = [a for a in trials["threat"] if a.proposed_class != "rotary-small"]
    others = ("fixed-wing-small", "bird", "unknown")
    for label in others:
        share = rate(sum(a.proposed_class == label for a in got), len(got))
        assert abs(share - 1 / 3) < five_sigma(1 / 3, len(got))
    assert all(a.proposed_class in others for a in got)


def test_confidence_is_higher_when_the_flag_is_correct(trials: dict[str, Any]) -> None:
    config: AssistConfig = trials["config"]
    everything = trials["threat"] + trials["bird"] + trials["false"]
    right = [a.confidence for a in everything if a.correct_flag]
    wrong = [a.confidence for a in everything if not a.correct_flag]
    assert right and wrong
    mean_right = sum(right) / len(right)
    mean_wrong = sum(wrong) / len(wrong)
    assert mean_right > mean_wrong + 0.2
    # Clamping at 0.99 pulls the correct-flag mean a little below its configured centre.
    assert abs(mean_right - config.confidence_correct_mean) < 0.02
    assert abs(mean_wrong - config.confidence_wrong_mean) < 0.02
    assert all(0.05 <= a.confidence <= 0.99 for a in everything)
    assert all(round(a.confidence, 3) == a.confidence for a in everything)


def test_confidence_is_clamped_to_its_bounds() -> None:
    wide = AssistConfig(
        confidence_correct_mean=0.99, confidence_wrong_mean=0.05, confidence_sigma=1.0
    )
    got = run_trials(AiAssist(SEED, wide), DRONE, tracks=2000, epochs=1)
    values = {a.confidence for a in got}
    assert min(values) == 0.05
    assert max(values) == 0.99


def test_confidence_with_zero_sigma_is_the_configured_mean() -> None:
    flat = AssistConfig(confidence_sigma=0.0, hit_rate=1.0, false_alarm_rate=0.0)
    got = run_trials(AiAssist(SEED, flat), DRONE, tracks=50, epochs=1)
    assert {a.confidence for a in got} == {0.8}


# --- the keyed uniform ----------------------------------------------------------------------


def test_keyed_uniform_is_in_unit_interval_and_roughly_uniform() -> None:
    n = 100000
    bins = [0] * 10
    for i in range(n):
        u = keyed_uniform(7, f"track-{i}", i % 5, "flag")
        assert 0.0 <= u < 1.0
        bins[int(u * 10)] += 1
    sigma = math.sqrt(n * 0.1 * 0.9)
    assert all(abs(count - n / 10) < 5 * sigma for count in bins), bins


def test_keyed_uniform_has_no_visible_correlation_between_purposes() -> None:
    n = 100000
    purposes = ("flag", "class", "pick", "conf0")
    series = {p: [keyed_uniform(11, f"x{i}", 0, p) for i in range(n)] for p in purposes}

    def corr(a: list[float], b: list[float]) -> float:
        ma, mb = sum(a) / n, sum(b) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((y - mb) ** 2 for y in b)
        return cov / math.sqrt(va * vb)

    limit = 5 / math.sqrt(n)  # a correlation of independent series has standard error 1 / sqrt(n)
    for i, p in enumerate(purposes):
        for q in purposes[i + 1 :]:
            assert abs(corr(series[p], series[q])) < limit, (p, q)


def test_keyed_uniform_encoding_is_unambiguous() -> None:
    assert keyed_uniform(1, "a", 1) != keyed_uniform(1, "a", "1")
    assert keyed_uniform(1, "a,b") != keyed_uniform(1, "a", "b")
    assert keyed_uniform(1, "a", 0, "flag") != keyed_uniform(2, "a", 0, "flag")
    assert keyed_uniform(1, "é") == keyed_uniform(1, "é")


# --- reproducibility ------------------------------------------------------------------------


def fingerprint(seed: int) -> str:
    """Instructor records for 25 tracks over 3 epochs, as canonical JSON."""
    assist = AiAssist(seed)
    truths = (DRONE, FIXED_WING, BIRD, FALSE_TRACK)
    records = []
    for epoch in range(3):
        for i in range(25):
            got = assist.assess(
                confirmed(f"T-{i:03d}"), truths[i % 4], 40 + epoch * TICKS_PER_ASSESSMENT
            )
            assert got is not None
            records.append(got.record())
    return json.dumps(records, sort_keys=True, separators=(",", ":"))


def test_same_seed_gives_identical_output_and_different_seeds_differ() -> None:
    assert fingerprint(5) == fingerprint(5)
    assert fingerprint(5) != fingerprint(6)


def test_output_is_identical_in_a_process_with_a_different_hash_salt() -> None:
    script = "from tests.test_tracking_assist import fingerprint; print(fingerprint(5))"
    done = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", script],
        cwd=API_DIR,
        env=os.environ | {"PYTHONHASHSEED": "4242"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == fingerprint(5)


def test_results_do_not_depend_on_the_order_of_calls() -> None:
    ids = [f"T-{i}" for i in range(30)]
    truths = {t: [DRONE, BIRD, FALSE_TRACK][i % 3] for i, t in enumerate(ids)}

    def tick_of(epoch: int) -> int:
        return epoch * TICKS_PER_ASSESSMENT

    def collect(order: list[tuple[str, int]]) -> dict[tuple[str, int], dict[str, Any]]:
        assist = AiAssist(SEED)
        out = {}
        for track, epoch in order:
            got = assist.assess(confirmed(track), truths[track], tick_of(epoch))
            assert got is not None
            out[(track, epoch)] = {k: v for k, v in got.record().items() if k != "tick"}
        return out

    epoch_major = [(t, e) for e in range(3) for t in ids]
    reversed_ = [(t, e) for e in range(3) for t in reversed(ids)]
    track_major = [(t, e) for t in reversed(ids) for e in range(3)]
    expected = collect(epoch_major)
    assert collect(reversed_) == expected
    assert collect(track_major) == expected


def test_each_epoch_of_a_track_gets_fresh_draws() -> None:
    assist = AiAssist(SEED)
    got = [assist.assess(confirmed("T"), DRONE, e * TICKS_PER_ASSESSMENT) for e in range(40)]
    assert len({a.confidence for a in got if a is not None}) > 10


# --- what the trainee may see ---------------------------------------------------------------


def test_view_carries_no_truth_and_record_does() -> None:
    assist = AiAssist(SEED)
    expected_view = {
        "track",
        "tick",
        "flag",
        "proposed_class",
        "confidence",
        "source",
        "basis",
        "data_status",
    }
    seen_wrong_class = 0
    for n, truth in enumerate((DRONE, FIXED_WING, BIRD, FALSE_TRACK)):
        for i in range(300):
            got = assist.assess(confirmed(f"T-{n}-{i}"), truth, 10)
            assert got is not None
            view = got.view()
            assert set(view) == expected_view
            assert not LEAK_KEYS & set(view)
            record = got.record()
            assert LEAK_KEYS - {"truth"} <= set(record)
            assert record["true_class"] == truth.class_id
            assert {k: record[k] for k in expected_view} == view
            json.dumps(view)
            if truth.class_id and got.proposed_class != truth.class_id:
                seen_wrong_class += 1
                assert truth.class_id not in json.dumps(view)
    assert seen_wrong_class > 0


def test_every_output_is_labelled_reference_and_simulated_even_for_a_verified_track() -> None:
    assist = AiAssist(SEED)
    got = assist.assess(confirmed("T", data_status="verified"), DRONE, 0)
    assert got is not None
    view = got.view()
    assert view["data_status"] == "reference"
    assert view["source"] == "simulated assist"
    assert view["basis"] == "configured hit and false-alarm rates; no real detector"
    assert view["flag"] in ("threat", "no-threat")
    assert view["track"] == "T"
    assert view["tick"] == 0


def test_true_class_outside_the_label_pool_is_handled() -> None:
    assist = AiAssist(SEED, AssistConfig(class_accuracy=0.0))
    got = assist.assess(confirmed("T"), TruthRef("quad-x"), 0)
    assert got is not None
    assert got.proposed_class in AssistConfig().labels


# --- threats and non-threats ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("class_id", "expected"),
    [
        ("rotary-small", True),
        ("fixed-wing-small", True),
        ("unknown", True),
        ("bird", False),
        ("kite", False),
        ("balloon", False),
        ("fpv-small", True),
        (None, False),
    ],
)
def test_is_threat(class_id: str | None, expected: bool) -> None:
    assert is_threat(class_id) is expected


def test_non_threat_set_is_the_clutter_classes_of_the_operator_vocabulary() -> None:
    assert frozenset({"bird", "kite", "balloon"}) == NON_THREAT_CLASSES


def test_birds_and_false_tracks_use_the_false_alarm_rate_and_drones_the_hit_rate() -> None:
    always_right = AiAssist(SEED, AssistConfig(hit_rate=1.0, false_alarm_rate=0.0))
    always_wrong = AiAssist(SEED, AssistConfig(hit_rate=0.0, false_alarm_rate=1.0))
    for i in range(50):
        for truth, is_drone in (
            (DRONE, True),
            (FIXED_WING, True),
            (BIRD, False),
            (FALSE_TRACK, False),
        ):
            a = always_right.assess(confirmed(f"T{i}"), truth, 0)
            b = always_wrong.assess(confirmed(f"T{i}"), truth, 0)
            assert a is not None
            assert b is not None
            assert a.threat is is_drone
            assert a.correct_flag
            assert b.threat is (not is_drone)
            assert not b.correct_flag
            always_right.forget(f"T{i}")
            always_wrong.forget(f"T{i}")


def test_a_false_track_is_called_unknown_when_the_class_is_right() -> None:
    perfect = AiAssist(SEED, AssistConfig(class_accuracy=1.0))
    broken = AiAssist(SEED, AssistConfig(class_accuracy=0.0))
    for i in range(100):
        a = perfect.assess(confirmed(f"T{i}"), FALSE_TRACK, 0)
        b = broken.assess(confirmed(f"T{i}"), FALSE_TRACK, 0)
        assert a is not None
        assert b is not None
        assert a.proposed_class == "unknown"
        assert b.proposed_class != "unknown"
        assert b.proposed_class in AssistConfig().labels
        assert a.true_class is None


# --- due logic and state --------------------------------------------------------------------


@pytest.mark.parametrize("status", ["tentative", "coasting", "lost", ""])
def test_a_track_that_is_not_confirmed_is_not_assessed_and_consumes_nothing(status: str) -> None:
    assist = AiAssist(SEED)
    assert assist.assess({"id": "T", "status": status}, DRONE, 0) is None
    assert assist.assess({"id": "T"}, DRONE, 0) is None
    assert assist.state() == {"tracks": {}}
    first = assist.assess(confirmed("T"), DRONE, 3)
    fresh = AiAssist(SEED).assess(confirmed("T"), DRONE, 3)
    assert first == fresh


def test_reassessment_is_spaced_by_exactly_reassess_s_in_ticks() -> None:
    assist = AiAssist(SEED)
    start = 37
    first = assist.assess(confirmed("T"), DRONE, start)
    assert first is not None
    assert first.tick == start
    for tick in (start, start + 1, start + 50, start + TICKS_PER_ASSESSMENT - 1):
        assert assist.assess(confirmed("T"), DRONE, tick) is None
    assert assist.state()["tracks"]["T"] == {"epoch": 1, "last_tick": start}
    second = assist.assess(confirmed("T"), DRONE, start + TICKS_PER_ASSESSMENT)
    assert second is not None
    assert assist.state()["tracks"]["T"] == {"epoch": 2, "last_tick": start + TICKS_PER_ASSESSMENT}
    # A late call restarts the clock from when it actually ran.
    assert assist.assess(confirmed("T"), DRONE, start + 2 * TICKS_PER_ASSESSMENT - 1) is None
    late = start + 2 * TICKS_PER_ASSESSMENT + 40
    assert assist.assess(confirmed("T"), DRONE, late) is not None
    assert assist.assess(confirmed("T"), DRONE, late + TICKS_PER_ASSESSMENT - 1) is None
    assert assist.assess(confirmed("T"), DRONE, late + TICKS_PER_ASSESSMENT) is not None


@pytest.mark.parametrize(("reassess_s", "ticks"), [(0.5, 10), (1.0, 20), (0.04, 1), (12.5, 250)])
def test_the_interval_follows_the_configured_seconds_at_twenty_hertz(
    reassess_s: float, ticks: int
) -> None:
    assist = AiAssist(SEED, AssistConfig(reassess_s=reassess_s))
    assert assist.assess(confirmed("T"), DRONE, 0) is not None
    if ticks > 1:
        assert assist.assess(confirmed("T"), DRONE, ticks - 1) is None
    assert assist.assess(confirmed("T"), DRONE, ticks) is not None


def test_tracks_are_independent_and_forget_resets_the_epoch() -> None:
    assist = AiAssist(SEED)
    a0 = assist.assess(confirmed("A"), DRONE, 0)
    assert assist.assess(confirmed("B"), BIRD, 1) is not None
    assert assist.assess(confirmed("A"), DRONE, 10) is None
    assist.forget("A")
    assert set(assist.state()["tracks"]) == {"B"}
    again = assist.assess(confirmed("A"), DRONE, 10)
    assert again is not None
    assert a0 is not None
    assert (again.confidence, again.proposed_class) == (a0.confidence, a0.proposed_class)
    assert assist.state()["tracks"]["A"]["epoch"] == 1
    assist.forget("never-seen")


def test_state_round_trips_through_json_and_a_restored_assist_continues_identically() -> None:
    live = AiAssist(SEED)
    ids = [f"T-{i}" for i in range(6)]
    for i, t in enumerate(ids):
        live.assess(confirmed(t), DRONE if i % 2 else BIRD, i)
    state = json.loads(json.dumps(live.state()))
    assert state == live.state()
    assert list(state["tracks"]) == sorted(state["tracks"])

    twin = AiAssist(SEED)
    twin.restore(state)
    assert twin.state() == live.state()
    for tick in (50, 100, 105, 106, 205, 300):
        for i, t in enumerate(ids):
            truth = DRONE if i % 2 else BIRD
            assert twin.assess(confirmed(t), truth, tick) == live.assess(confirmed(t), truth, tick)
    assert twin.state() == live.state()


def test_restore_replaces_what_was_there() -> None:
    assist = AiAssist(SEED)
    assist.assess(confirmed("old"), DRONE, 0)
    assist.restore({"tracks": {"new": {"epoch": 2, "last_tick": 7}}})
    assert assist.state() == {"tracks": {"new": {"epoch": 2, "last_tick": 7}}}


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"tracks": 5},
        {"tracks": {"T": {"epoch": 1}}},
        {"tracks": {"T": {"epoch": "x", "last_tick": 0}}},
        {"tracks": {"T": {"epoch": 0, "last_tick": 0}}},
    ],
)
def test_restore_refuses_a_malformed_snapshot(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="AI assist state"):
        AiAssist(SEED).restore(bad)


# --- configuration --------------------------------------------------------------------------


def test_default_config_values_and_state() -> None:
    cfg = AssistConfig()
    assert cfg.to_state() == {
        "hit_rate": 0.90,
        "false_alarm_rate": 0.08,
        "class_accuracy": 0.85,
        "labels": ["rotary-small", "fixed-wing-small", "bird", "unknown"],
        "confidence_correct_mean": 0.80,
        "confidence_wrong_mean": 0.55,
        "confidence_sigma": 0.12,
        "reassess_s": 5.0,
    }
    json.dumps(cfg.to_state())
    assert AiAssist(1).config == cfg


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"hit_rate": 1.01}, "hit_rate"),
        ({"hit_rate": -0.1}, "hit_rate"),
        ({"false_alarm_rate": 2.0}, "false_alarm_rate"),
        ({"class_accuracy": float("nan")}, "class_accuracy"),
        ({"confidence_correct_mean": 1.0}, "confidence_correct_mean"),
        ({"confidence_wrong_mean": 0.01}, "confidence_wrong_mean"),
        ({"confidence_sigma": -0.1}, "confidence_sigma"),
        ({"confidence_sigma": float("inf")}, "confidence_sigma"),
        ({"reassess_s": 0.0}, "reassess_s"),
        ({"reassess_s": float("nan")}, "reassess_s"),
        ({"labels": ("bird",)}, "labels"),
        ({"labels": ()}, "labels"),
        ({"labels": ("bird", "bird")}, "labels"),
        ({"labels": ("bird", "")}, "empty"),
    ],
)
def test_config_validation(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        AssistConfig(**overrides)


def test_config_edges_are_allowed() -> None:
    AssistConfig(hit_rate=0.0, false_alarm_rate=1.0, class_accuracy=0.0, confidence_sigma=0.0)
    AssistConfig(confidence_correct_mean=0.05, confidence_wrong_mean=0.99)
