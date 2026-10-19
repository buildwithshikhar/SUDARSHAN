"""The anti-rote filter: a candidate too close to a trainee's history is rejected."""

import math

import pytest

from app.scenarios.diversity import THRESHOLD, K, check, distance
from app.scenarios.features import AXES, Features


def vec(*values: float) -> Features:
    return Features(tuple(values) + (0.0,) * (len(AXES) - len(values)))


def test_distance_is_zero_for_the_same_scenario_and_one_for_opposite_corners() -> None:
    a = vec(0.2, 0.4)
    assert distance(a, a) == 0.0
    assert distance(Features((0.0,) * 8), Features((1.0,) * 8)) == pytest.approx(1.0)
    assert distance(vec(0.0), vec(0.5)) == pytest.approx(0.5 / math.sqrt(8))


def test_distance_is_symmetric() -> None:
    a, b = vec(0.1, 0.9, 0.3), vec(0.7, 0.2, 0.5)
    assert distance(a, b) == distance(b, a)


def test_with_no_history_nothing_is_rejected() -> None:
    result = check(vec(0.5), [])
    assert (result.history_size, result.novelty, result.passes, result.nearest) == (
        0,
        None,
        None,
        (),
    )
    assert result.threshold == THRESHOLD


def test_a_candidate_closer_than_the_threshold_to_the_history_is_rejected() -> None:
    history = [vec(0.5, 0.5), vec(0.52, 0.5), vec(0.5, 0.51)]
    close = check(vec(0.5, 0.5), history)
    assert close.passes is False and close.novelty is not None and close.novelty < THRESHOLD
    far = check(vec(0.0, 0.0), history)
    assert far.passes is True and far.novelty is not None and far.novelty >= THRESHOLD


def test_the_novelty_is_the_mean_of_the_k_nearest() -> None:
    history = [vec(0.0), vec(0.1), vec(0.2), vec(1.0)]
    result = check(vec(0.0), history, threshold=0.0)
    nearest = [d for _, d in result.nearest]
    assert len(nearest) == K == 3
    assert result.novelty == pytest.approx(sum(nearest) / 3, abs=1e-6)
    assert [i for i, _ in result.nearest] == [0, 1, 2]  # nearest first, the far one left out


def test_with_fewer_than_k_entries_all_are_used() -> None:
    result = check(vec(0.0), [vec(0.4)], threshold=0.0)
    assert len(result.nearest) == 1 and result.novelty == result.nearest[0][1]


def test_a_tie_in_distance_goes_to_the_earlier_history_entry() -> None:
    result = check(vec(0.5), [vec(0.4), vec(0.6)], threshold=0.0, k=1)
    assert result.nearest[0][0] == 0


def test_the_threshold_is_the_callers_and_the_boundary_passes() -> None:
    history = [vec(0.0)]
    candidate = vec(0.4)
    novelty = check(candidate, history).novelty
    assert novelty is not None
    assert check(candidate, history, threshold=novelty).passes is True
    assert check(candidate, history, threshold=novelty + 1e-6).passes is False
