"""Class confusion: what a sensor reports for each true class.

Rows are probabilities that sum to 1 (the contract refuses anything else). Sampling walks the
labels in file order against one uniform draw, so the result depends only on the draw.
"""

from app.contracts.sensor_profile import ConfusionTable


class ConfusionMatrix:
    def __init__(self, table: ConfusionTable) -> None:
        self.table = table
        self.labels = tuple(table.labels)

    @property
    def classes(self) -> tuple[str, ...]:
        """True classes this matrix has a row for."""
        return tuple(self.table.rows)

    def has(self, true_class: str) -> bool:
        return true_class in self.table.rows

    def row(self, true_class: str) -> tuple[float, ...]:
        try:
            return tuple(self.table.rows[true_class])
        except KeyError:
            raise KeyError(f"confusion table has no row for class {true_class!r}") from None

    def sample(self, true_class: str, u: float) -> str:
        """Label reported for `true_class` given a uniform draw `u` in [0, 1)."""
        cumulative = 0.0
        last = self.labels[0]
        for label, p in zip(self.labels, self.row(true_class), strict=True):
            if p > 0.0:
                last = label
            cumulative += p
            if u < cumulative:
                return label
        return last  # u landed in the rounding gap above the final cumulative sum
