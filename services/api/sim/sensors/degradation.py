"""Degradations: time-limited conditions that make a sensor worse.

A degradation is data (a kind, a window, a severity), so it can come from a scenario or from an
instructor inject and be replayed. The framework handles the two universal kinds, `outage` and
`sector-outage`. Every other kind is interpreted by the sensor model, which returns the `Effects`
it has on that modality (haze matters to EO/IR, interference to RF, and so on) or `None` when the
modality is not affected.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .. import detmath

KINDS = ("outage", "sector-outage", "clutter", "haze", "glare", "interference", "wind-noise")


@dataclass(frozen=True, slots=True)
class Degradation:
    sensor_id: str
    kind: str
    start_tick: int
    #: First tick the degradation no longer applies; `None` lasts to the end of the session.
    end_tick: int | None = None
    #: 0 (no effect) to 1 (worst the model represents). `outage` kinds ignore it.
    severity: float = 1.0
    #: Clockwise sector blocked by `sector-outage`, compass degrees.
    sector_from_deg: float | None = None
    sector_to_deg: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown degradation kind {self.kind!r}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("degradation severity must be within [0, 1]")
        if self.start_tick < 0 or (self.end_tick is not None and self.end_tick <= self.start_tick):
            raise ValueError("degradation window must end after it starts")
        has_sector = self.sector_from_deg is not None and self.sector_to_deg is not None
        if (self.kind == "sector-outage") != has_sector:
            raise ValueError("a sector is required for sector-outage and only for sector-outage")

    def active(self, tick: int) -> bool:
        return self.start_tick <= tick and (self.end_tick is None or tick < self.end_tick)

    def to_state(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "kind": self.kind,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "severity": self.severity,
            "sector_from_deg": self.sector_from_deg,
            "sector_to_deg": self.sector_to_deg,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "Degradation":
        return cls(**state)


@dataclass(frozen=True, slots=True)
class Effects:
    """The combined effect of the degradations active on one sensor at one tick."""

    outage: bool = False
    #: Blocked compass sectors, each (from, to) clockwise.
    blocked_sectors: tuple[tuple[float, float], ...] = ()
    #: Multiplies the probability of detection.
    pd_factor: float = 1.0
    #: Multiplies every measurement sigma.
    noise_factor: float = 1.0
    #: Multiplies the false-alarm rate.
    clutter_factor: float = 1.0

    def blocks(self, azimuth_deg: float) -> bool:
        return any(
            detmath.wrap360(azimuth_deg - start) <= detmath.wrap360(end - start)
            for start, end in self.blocked_sectors
        )

    def then(self, other: "Effects") -> "Effects":
        return Effects(
            self.outage or other.outage,
            self.blocked_sectors + other.blocked_sectors,
            self.pd_factor * other.pd_factor,
            self.noise_factor * other.noise_factor,
            self.clutter_factor * other.clutter_factor,
        )


def combine(effects: Iterable[Effects]) -> Effects:
    """Fold in the order given; the order is the order the degradations were injected."""
    total = Effects()
    for effect in effects:
        total = total.then(effect)
    return total
