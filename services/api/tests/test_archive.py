"""The MAP-Elites archive: cells, elites, coverage, QD-score, mean pairwise distance, heat map."""

import pytest

from app.scenarios.archive import ARCHIVE_AXES, CELLS, Archive, bin_labels, cell_of
from app.scenarios.diversity import distance
from app.scenarios.features import AXES, Features


def vec(**axes: float) -> Features:
    return Features(tuple(axes.get(a, 0.0) for a in AXES))


def test_the_grid_is_six_by_six_by_four() -> None:
    assert [(a, n) for a, n in ARCHIVE_AXES] == [
        ("threat_count", 6),
        ("id_ambiguity", 6),
        ("approach_speed", 4),
    ]
    assert CELLS == 144


def test_a_vector_falls_in_one_cell_and_one_goes_in_the_last_bin() -> None:
    assert cell_of(vec()) == (0, 0, 0)
    assert cell_of(vec(threat_count=0.5, id_ambiguity=0.34, approach_speed=0.6)) == (3, 2, 2)
    assert cell_of(vec(threat_count=1.0, id_ambiguity=1.0, approach_speed=1.0)) == (5, 5, 3)


def test_an_empty_archive_reports_zero_everything() -> None:
    a = Archive()
    assert a.metrics() == {
        "coverage": 0.0,
        "qd_score": 0.0,
        "mean_pairwise_distance": 0.0,
        "filled": 0,
        "total": 144,
    }
    assert a.elites() == []


def test_an_elite_keeps_its_cell_until_something_better_arrives() -> None:
    a = Archive()
    f = vec(threat_count=0.5)
    assert a.add("first", f, 0.8) is True
    assert a.add("same-quality", f, 0.8) is False  # a tie keeps the earlier
    assert a.add("worse", f, 0.7) is False
    assert a.add("better", f, 0.9) is True
    assert [e.scenario_id for e in a.elites()] == ["better"]


def test_coverage_qd_score_and_mean_pairwise_distance() -> None:
    a = Archive()
    f1, f2, f3 = vec(threat_count=0.0), vec(threat_count=0.5), vec(threat_count=1.0)
    for name, f, q in (("a", f1, 0.8), ("b", f2, 0.9), ("c", f3, 1.0)):
        a.add(name, f, q)
    assert a.coverage() == pytest.approx(3 / 144)
    assert a.qd_score() == pytest.approx(2.7)
    expected = (distance(f1, f2) + distance(f1, f3) + distance(f2, f3)) / 3
    assert a.mean_pairwise_distance() == pytest.approx(expected, abs=1e-6)
    m = a.metrics()
    assert (m["filled"], m["total"]) == (3, 144)


def test_one_elite_has_no_pairwise_distance() -> None:
    a = Archive()
    a.add("only", vec(), 1.0)
    assert a.mean_pairwise_distance() == 0.0


def test_the_heat_map_keeps_the_best_quality_over_the_third_axis() -> None:
    a = Archive()
    a.add("slow", vec(threat_count=0.5, id_ambiguity=0.5, approach_speed=0.1), 0.8)
    a.add("fast", vec(threat_count=0.5, id_ambiguity=0.5, approach_speed=0.9), 0.95)
    a.add("elsewhere", vec(threat_count=0.0, id_ambiguity=0.9, approach_speed=0.1), 0.85)
    heat = a.heatmap("threat_count", "id_ambiguity")
    values = heat["values"]
    assert len(values) == 6 and all(len(row) == 6 for row in values)  # rows are y, columns x
    assert values[3][3] == 0.95  # the better of the two that share (3, 3)
    assert values[5][0] == 0.85
    assert sum(v is not None for row in values for v in row) == 2
    swapped = a.heatmap("id_ambiguity", "approach_speed")
    assert len(swapped["values"]) == 4 and len(swapped["values"][0]) == 6


@pytest.mark.parametrize(
    ("x", "y"),
    [("threat_count", "threat_count"), ("nope", "id_ambiguity"), ("threat_count", "stealth")],
)
def test_the_heat_map_needs_two_different_archive_axes(x: str, y: str) -> None:
    with pytest.raises(ValueError, match="two different archive axes"):
        Archive().heatmap(x, y)


def test_the_archive_serialises_axes_cells_metrics_and_heat_map() -> None:
    a = Archive()
    a.add("s1", vec(threat_count=0.5), 0.9)
    body = a.to_dict("approach_speed", "threat_count")
    assert [ax["name"] for ax in body["axes"]] == ["threat_count", "id_ambiguity", "approach_speed"]
    assert body["axes"][0]["labels"] == ["0-17", "17-33", "33-50", "50-67", "67-83", "83-100"]
    assert body["cells"] == [{"index": [3, 0, 0], "quality": 0.9, "scenario_id": "s1"}]
    assert body["metrics"]["filled"] == 1
    assert (body["heatmap"]["x_axis"], body["heatmap"]["y_axis"]) == (
        "approach_speed",
        "threat_count",
    )
    assert bin_labels(4) == ["0-25", "25-50", "50-75", "75-100"]
