"""Detections and the random draws that make them.

Every candidate target consumes the same fixed number of draws from the `sensors` stream whether
or not it is detected, in range, or blocked by a degradation. Injecting an outage therefore never
shifts the noise a later target or sensor receives, and the stream position depends only on how
many sensor updates have run.
"""

from dataclasses import dataclass, field
from typing import Any

from ..rng import RngStreams

STREAM = "sensors"
#: Uniform numbers consumed per candidate target: detect, classify, then four 4-uniform noises.
DRAWS_PER_CANDIDATE = 2 + 4 * 4

FeatureValue = float | str | bool

#: `data_status` values on everything a trainee sees that is derived from sensor parameters.
DATA_REFERENCE = "reference"
DATA_VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class Draws:
    detect: float
    classify: float
    noise: tuple[float, float, float, float]

    @classmethod
    def take(cls, rng: RngStreams) -> "Draws":
        detect = rng.uniform(STREAM)
        classify = rng.uniform(STREAM)
        n = (
            rng.normalish(STREAM),
            rng.normalish(STREAM),
            rng.normalish(STREAM),
            rng.normalish(STREAM),
        )
        return cls(detect, classify, n)


@dataclass(frozen=True, slots=True)
class Detection:
    """One report from one sensor: noisy measurements, never ground truth.

    `truth_id` links a report to the drone that caused it, for scoring and the instructor view.
    It is `None` for a false alarm. It must never reach a trainee: use `trainee_view`, which is
    also the tracker's only input (docs/SENSOR_MODELS.md, "Tracking").
    """

    sensor_id: str
    modality: str
    tick: int
    truth_id: str | None
    azimuth_deg: float
    elevation_deg: float
    range_m: float | None = None
    radial_speed_mps: float | None = None
    #: One-sigma measurement uncertainty actually applied; the tracker uses it as its weight.
    sigma_range_m: float | None = None
    sigma_azimuth_deg: float | None = None
    sigma_elevation_deg: float | None = None
    reported_class: str | None = None
    #: Modality-specific cues (for example a micro-Doppler class, a hop-pattern flag).
    features: dict[str, FeatureValue] = field(default_factory=dict)
    #: True unless every parameter behind the report is `verified: true` (Q-20). Fails safe: a
    #: detection built without provenance is labelled as reference data.
    reference_data: bool = True

    @property
    def false_alarm(self) -> bool:
        return self.truth_id is None

    def payload(self) -> dict[str, Any]:
        """Instructor and log view: everything, rounded for readability."""
        data = self.trainee_view()
        data["truth_id"] = self.truth_id
        return data

    def trainee_view(self) -> dict[str, Any]:
        """What a trainee's console may show: no ground-truth reference.

        `data_status` is `"reference"` when any parameter behind the figures is still
        `verified: false` (Q-20): the console must then show them as reference data.
        """
        return {
            "sensor_id": self.sensor_id,
            "modality": self.modality,
            "tick": self.tick,
            "azimuth_deg": _r(self.azimuth_deg),
            "elevation_deg": _r(self.elevation_deg),
            "range_m": _r(self.range_m),
            "radial_speed_mps": _r(self.radial_speed_mps),
            "sigma_range_m": _r(self.sigma_range_m),
            "sigma_azimuth_deg": _r(self.sigma_azimuth_deg),
            "sigma_elevation_deg": _r(self.sigma_elevation_deg),
            "reported_class": self.reported_class,
            "features": {
                k: _r(v) if isinstance(v, float) else v for k, v in sorted(self.features.items())
            },
            "data_status": DATA_REFERENCE if self.reference_data else DATA_VERIFIED,
        }


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 3)
