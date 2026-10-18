"""`ErrorModel.difficulty`: more association errors, and exactly the old behaviour at the default."""

import pytest

from sim.tracking.ambiguity import ErrorModel, ErrorPolicy

from .tracking_cases import SWAP_SEED, SWAP_TICK, component, crossing

#: Two tracks and three reports with an alternative pairing (swap), a spare report (split) and a
#: second nominal pair (merge): all three error modes apply.
ALL_MODES = (("T1", 0, 1.0), ("T1", 1, 5.0), ("T2", 1, 1.5), ("T2", 0, 5.5), ("T1", 2, 9.0))
ERROR_MODES = ("swap", "split", "merge")


def probabilities(model: ErrorModel) -> dict[str, float]:
    return {o.mode: o.probability for o in ErrorPolicy(model).options(component(*ALL_MODES))}


def test_the_default_difficulty_is_one_and_changes_nothing() -> None:
    assert ErrorModel().difficulty == 1.0
    assert probabilities(ErrorModel(difficulty=1.0)) == probabilities(ErrorModel())
    assert set(probabilities(ErrorModel())) == set(ERROR_MODES)


def test_the_default_run_is_the_documented_one() -> None:
    # The documented swap (seed 1014, ledger tick 648) is unchanged by the new parameter.
    run = crossing(SWAP_SEED, ErrorPolicy(ErrorModel()), ticks=SWAP_TICK + 1)
    assert run.kinds()[0] == (SWAP_TICK, "swap")


def test_difficulty_scales_every_error_probability() -> None:
    base = probabilities(ErrorModel())
    harder = probabilities(ErrorModel(difficulty=1.5))
    easier = probabilities(ErrorModel(difficulty=0.5))
    for mode, p in base.items():
        assert harder[mode] == pytest.approx(1.5 * p)
        assert easier[mode] == pytest.approx(0.5 * p)


def test_difficulty_zero_removes_every_error() -> None:
    assert probabilities(ErrorModel(difficulty=0.0)) == {}
    policy = ErrorPolicy(ErrorModel(difficulty=0.0))
    comp = component(*ALL_MODES)
    for draw in (0.0, 0.3, 0.999999):
        assert policy.resolve(comp, draw).mode == "nominal"


def test_a_large_difficulty_keeps_the_probabilities_a_distribution() -> None:
    base = probabilities(ErrorModel())
    huge = probabilities(ErrorModel(difficulty=50.0))
    assert sum(huge.values()) == pytest.approx(1.0)
    for a in base:  # shrunk in proportion, so the ratios between modes stay the same
        for b in base:
            assert huge[a] / huge[b] == pytest.approx(base[a] / base[b])


@pytest.mark.parametrize("bad", [-0.1, float("nan")])
def test_a_negative_or_undefined_difficulty_is_refused(bad: float) -> None:
    with pytest.raises(ValueError, match="difficulty cannot be negative"):
        ErrorModel(difficulty=bad)


def test_difficulty_never_creates_errors_where_the_structure_allows_none() -> None:
    lone = component(("T1", 0, 1.0))
    assert ErrorPolicy(ErrorModel(difficulty=50.0)).options(lone) == []


def errors_on_the_crossing(difficulty: float, seeds: range) -> int:
    policy = ErrorPolicy(ErrorModel(difficulty=difficulty))
    total = 0
    for seed in seeds:
        modes = crossing(seed, policy, ticks=700).modes()
        total += sum(modes.get(m, 0) for m in ERROR_MODES)
    return total


def test_a_higher_difficulty_gives_more_errors_on_the_crossing() -> None:
    seeds = range(40)
    default = errors_on_the_crossing(1.0, seeds)
    assert errors_on_the_crossing(0.0, seeds) == 0
    assert 0 < default < errors_on_the_crossing(2.5, seeds)


def test_difficulty_is_deterministic_for_a_seed() -> None:
    first = crossing(9, ErrorPolicy(ErrorModel(difficulty=2.5)), ticks=700)
    second = crossing(9, ErrorPolicy(ErrorModel(difficulty=2.5)), ticks=700)
    assert first.kinds() == second.kinds() and first.modes() == second.modes()
