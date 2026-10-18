"""Signal-detection metrics against reference values (z tables), with the log-linear correction.

The reference numbers come from standard normal quantiles worked out independently of the code
(bisection on `math.erf`), for example d' = z(0.9) - z(0.1) = 2 x 1.28155 = 2.5631.
"""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.scoring.sdt import metrics


@pytest.mark.parametrize(
    ("hits", "signals", "false_alarms", "noise", "d_prime", "criterion"),
    [
        (9, 10, 1, 10, 2.5631, 0.0),
        (8, 10, 2, 10, 1.6832, 0.0),
        (5, 10, 5, 10, 0.0, 0.0),
        (84134, 100000, 15866, 100000, 2.0, 0.0),
        # a liberal observer: H = 0.95, FA = 0.5: d' = 1.6449, c = -z(0.95) / 2
        (19, 20, 10, 20, 1.6449, -0.8224),
        # a conservative one: H = 0.5, FA = 0.05
        (10, 20, 1, 20, 1.6449, 0.8224),
    ],
)
def test_d_prime_and_criterion_match_reference_values(
    hits: int, signals: int, false_alarms: int, noise: int, d_prime: float, criterion: float
) -> None:
    sdt = metrics(hits, signals, false_alarms, noise)
    assert sdt.d_prime == pytest.approx(d_prime, abs=1e-3)
    assert sdt.criterion == pytest.approx(criterion, abs=1e-3)
    assert sdt.corrected is False
    assert sdt.hit_rate_used == sdt.hit_rate and sdt.false_alarm_rate_used == sdt.false_alarm_rate


def test_the_exact_reference_values_round_to_four_places() -> None:
    assert metrics(9, 10, 1, 10).d_prime == 2.5631
    assert metrics(8, 10, 2, 10).d_prime == 1.6832
    assert metrics(5, 10, 5, 10).d_prime == 0.0


def test_the_criterion_is_zero_when_the_hit_rate_is_one_minus_the_false_alarm_rate() -> None:
    for hits, false_alarms in [(9, 1), (8, 2), (7, 3), (6, 4), (1, 9)]:
        assert metrics(hits, 10, false_alarms, 10).criterion == pytest.approx(0.0, abs=1e-9)


def test_rates_and_trial_counts_are_reported() -> None:
    sdt = metrics(3, 4, 1, 5)
    assert (sdt.signal_trials, sdt.noise_trials) == (4, 5)
    assert (sdt.hits, sdt.misses, sdt.false_alarms, sdt.correct_rejections) == (3, 1, 1, 4)
    assert (sdt.hit_rate, sdt.false_alarm_rate) == (0.75, 0.2)


# ------------------------------------------------------------------------- log-linear correction


def test_ten_of_ten_hits_and_no_false_alarms_use_the_log_linear_estimates() -> None:
    sdt = metrics(10, 10, 0, 10)
    assert sdt.corrected is True
    assert (sdt.hit_rate, sdt.false_alarm_rate) == (1.0, 0.0)
    assert sdt.hit_rate_used == pytest.approx(10.5 / 11, abs=1e-4)
    assert sdt.false_alarm_rate_used == pytest.approx(0.5 / 11, abs=1e-4)
    assert sdt.d_prime == pytest.approx(3.3812, abs=1e-4)
    assert sdt.criterion == pytest.approx(0.0, abs=1e-9)


def test_no_hits_and_every_noise_trial_a_false_alarm_gives_the_mirror_image() -> None:
    sdt = metrics(0, 10, 10, 10)
    assert sdt.corrected is True
    assert sdt.d_prime == pytest.approx(-3.3812, abs=1e-4)


def test_a_rate_of_zero_or_one_corrects_both_rates() -> None:
    perfect_hits = metrics(5, 5, 2, 10)  # H = 1, FA = 0.2: both replaced
    assert perfect_hits.corrected is True
    assert perfect_hits.hit_rate_used == pytest.approx(5.5 / 6, abs=1e-4)
    assert perfect_hits.false_alarm_rate_used == pytest.approx(2.5 / 11, abs=1e-4)
    no_alarms = metrics(3, 5, 0, 4)  # H = 0.6, FA = 0: both replaced
    assert no_alarms.corrected is True
    assert no_alarms.hit_rate_used == pytest.approx(3.5 / 6, abs=1e-4)
    assert no_alarms.false_alarm_rate_used == pytest.approx(0.5 / 5, abs=1e-4)


def test_one_hit_in_one_signal_trial_with_two_noise_trials_and_no_alarm() -> None:
    sdt = metrics(1, 1, 0, 2)
    assert sdt.d_prime == pytest.approx(1.6419, abs=1e-4)
    assert sdt.criterion == pytest.approx(0.1465, abs=1e-4)


def test_one_signal_and_one_noise_trial_gives_the_smallest_corrected_pair() -> None:
    sdt = metrics(1, 1, 0, 1)
    assert (sdt.hit_rate_used, sdt.false_alarm_rate_used) == (0.75, 0.25)
    assert sdt.d_prime == pytest.approx(1.3490, abs=1e-4)
    both_wrong = metrics(1, 1, 1, 1)  # H = 1, FA = 1: d' = 0, c = -z(0.75)
    assert both_wrong.d_prime == 0.0
    assert both_wrong.criterion == pytest.approx(-0.6745, abs=1e-4)


# ------------------------------------------------------------------------------ no d' available


def test_no_signal_trials_means_no_hit_rate_and_no_d_prime() -> None:
    sdt = metrics(0, 0, 1, 4)
    assert sdt.hit_rate is None and sdt.hit_rate_used is None
    assert sdt.false_alarm_rate == 0.25
    assert sdt.d_prime is None and sdt.criterion is None and sdt.corrected is False


def test_no_noise_trials_means_no_false_alarm_rate_and_no_d_prime() -> None:
    sdt = metrics(2, 3, 0, 0)
    assert sdt.false_alarm_rate is None and sdt.false_alarm_rate_used is None
    assert sdt.hit_rate == pytest.approx(0.6667, abs=1e-4)
    assert sdt.d_prime is None and sdt.criterion is None and sdt.corrected is False


def test_no_trials_at_all() -> None:
    sdt = metrics(0, 0, 0, 0)
    assert sdt.model_dump(exclude={"signal_trials", "noise_trials"}) == {
        "hits": 0,
        "misses": 0,
        "false_alarms": 0,
        "correct_rejections": 0,
        "hit_rate": None,
        "false_alarm_rate": None,
        "corrected": False,
        "hit_rate_used": None,
        "false_alarm_rate_used": None,
        "d_prime": None,
        "criterion": None,
    }


# ----------------------------------------------------------------------------- argument checks


@pytest.mark.parametrize(
    "args", [(3, 2, 0, 4), (0, 2, 5, 4), (-1, 2, 0, 4), (1, 2, -1, 4), (0, -1, 0, 4), (0, 2, 0, -1)]
)
def test_counts_that_do_not_fit_their_trials_are_refused(args: tuple[int, int, int, int]) -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        metrics(*args)


# --------------------------------------------------------------------------------- properties


@given(
    st.integers(0, 40),
    st.integers(0, 40),
    st.integers(0, 40),
    st.integers(0, 40),
)
def test_metrics_are_finite_ordered_and_consistent(a: int, b: int, c: int, d: int) -> None:
    hits, signals = min(a, b), max(a, b)
    false_alarms, noise = min(c, d), max(c, d)
    sdt = metrics(hits, signals, false_alarms, noise)
    assert sdt.misses == signals - hits and sdt.correct_rejections == noise - false_alarms
    for value in (sdt.d_prime, sdt.criterion):
        assert value is None or math.isfinite(value)
    if sdt.d_prime is not None:
        assert (sdt.hit_rate_used or 0) > 0 and (sdt.false_alarm_rate_used or 0) > 0
        # more hits at the same false alarms never lowers d' (when neither is corrected)
        more = metrics(hits + 1, signals, false_alarms, noise) if hits < signals else None
        if more is not None and not more.corrected and not sdt.corrected:
            assert (more.d_prime or 0.0) >= sdt.d_prime
