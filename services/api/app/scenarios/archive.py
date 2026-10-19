"""A MAP-Elites archive over three feature axes, with the metrics that say how much of the space
the scenarios cover (Mouret and Clune 2015; Pugh et al. 2016).

The grid is `threat_count` x `id_ambiguity` x `approach_speed`, 6 x 6 x 4 = 144 cells. Each cell
keeps the best scenario that fell in it, best being the highest quality (the oracle's lowest
hostile contact score); a tie keeps the earlier. Reported: coverage (filled cells over all cells),
QD-score (the sum of the elites' quality) and the mean pairwise distance of the elites in the full
eight-axis feature space. The expressive-range heat map is one pair of axes with the best quality
over the third.
"""

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from .diversity import distance
from .features import Features

#: The archive axes and their bin counts.
ARCHIVE_AXES: tuple[tuple[str, int], ...] = (
    ("threat_count", 6),
    ("id_ambiguity", 6),
    ("approach_speed", 4),
)
CELLS = math.prod(bins for _, bins in ARCHIVE_AXES)


@dataclass(frozen=True, slots=True)
class Elite:
    scenario_id: str
    quality: float
    features: Features
    index: tuple[int, int, int]


def cell_of(features: Features) -> tuple[int, int, int]:
    """The grid cell a feature vector falls in; a value of exactly 1 goes in the last bin."""
    (a, na), (b, nb), (c, nc) = ARCHIVE_AXES
    return (
        min(na - 1, math.floor(features[a] * na)),
        min(nb - 1, math.floor(features[b] * nb)),
        min(nc - 1, math.floor(features[c] * nc)),
    )


@dataclass(slots=True)
class Archive:
    cells: dict[tuple[int, int, int], Elite] = field(default_factory=dict)

    def add(self, scenario_id: str, features: Features, quality: float) -> bool:
        """Offer a scenario; True if it took its cell (the cell was empty or it is better)."""
        index = cell_of(features)
        held = self.cells.get(index)
        if held is not None and quality <= held.quality:
            return False
        self.cells[index] = Elite(scenario_id, quality, features, index)
        return True

    def elites(self) -> list[Elite]:
        return [self.cells[i] for i in sorted(self.cells)]

    def coverage(self) -> float:
        return len(self.cells) / CELLS

    def qd_score(self) -> float:
        return round(sum(e.quality for e in self.cells.values()), 6)

    def mean_pairwise_distance(self) -> float:
        """Mean feature distance over all pairs of elites; 0 with fewer than two."""
        elites = self.elites()
        if len(elites) < 2:
            return 0.0
        pairs = list(combinations(elites, 2))
        return round(sum(distance(a.features, b.features) for a, b in pairs) / len(pairs), 6)

    def metrics(self) -> dict[str, float | int]:
        return {
            "coverage": round(self.coverage(), 6),
            "qd_score": self.qd_score(),
            "mean_pairwise_distance": self.mean_pairwise_distance(),
            "filled": len(self.cells),
            "total": CELLS,
        }

    def heatmap(self, x_axis: str, y_axis: str) -> dict[str, Any]:
        """Best quality per (x, y) bin over the third axis; `None` marks an empty bin."""
        names = [a for a, _ in ARCHIVE_AXES]
        if x_axis not in names or y_axis not in names or x_axis == y_axis:
            raise ValueError(f"heat-map axes must be two different archive axes: {names}")
        xi, yi = names.index(x_axis), names.index(y_axis)
        xb, yb = ARCHIVE_AXES[xi][1], ARCHIVE_AXES[yi][1]
        values: list[list[float | None]] = [[None] * xb for _ in range(yb)]
        for index, elite in self.cells.items():
            x, y = index[xi], index[yi]
            held = values[y][x]
            if held is None or elite.quality > held:
                values[y][x] = elite.quality
        return {"x_axis": x_axis, "y_axis": y_axis, "values": values}

    def to_dict(self, x_axis: str = "threat_count", y_axis: str = "id_ambiguity") -> dict[str, Any]:
        return {
            "axes": [
                {"name": name, "bins": bins, "labels": bin_labels(bins)}
                for name, bins in ARCHIVE_AXES
            ],
            "cells": [
                {
                    "index": list(e.index),
                    "quality": e.quality,
                    "scenario_id": e.scenario_id,
                }
                for e in self.elites()
            ],
            "metrics": self.metrics(),
            "heatmap": self.heatmap(x_axis, y_axis),
        }


def bin_labels(bins: int) -> list[str]:
    """Human-readable bin ranges as percentages of the axis, for example `0-17`."""
    return [f"{round(100 * i / bins)}-{round(100 * (i + 1) / bins)}" for i in range(bins)]
