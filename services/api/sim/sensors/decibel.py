"""Decibel arithmetic for link-budget style models, built only from `sim.detmath`.

`math.log10` and `10 ** x` come from the platform maths library, so RF and acoustic models use the
natural-log based forms below. The two 10-based constants are correctly rounded divisions.
"""

from .. import detmath

LN10 = 2.302585092994046
#: 20 * log10(x) = DB20 * ln(x); 10 * log10(x) = DB10 * ln(x).
DB20 = 20.0 / LN10
DB10 = 10.0 / LN10


def amplitude_db(ratio: float) -> float:
    """Decibels of an amplitude (voltage, pressure, distance) ratio; `ratio` must be positive."""
    return DB20 * detmath.log(ratio)


def power_db(ratio: float) -> float:
    """Decibels of a power ratio; `ratio` must be positive."""
    return DB10 * detmath.log(ratio)


def db_to_amplitude(db: float) -> float:
    return detmath.exp(db / DB20)


def db_to_power(db: float) -> float:
    return detmath.exp(db / DB10)


def sigmoid(x: float) -> float:
    """Logistic function: a smooth, monotonic step from 0 to 1 used for probability of detection."""
    return 1.0 / (1.0 + detmath.exp(-x))
