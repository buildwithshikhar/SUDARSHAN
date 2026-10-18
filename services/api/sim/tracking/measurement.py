"""The tracker's only input: a detection as a trainee's console would see it.

`Measurement.from_view` is built from `Detection.trainee_view()`. It refuses a dict that carries a
ground-truth reference, so the tracker algorithm cannot depend on one; the truth ledger receives
ground truth through a separate channel and never feeds it back (docs/SENSOR_MODELS.md, "Tracking").
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from ..sensors.detection import DATA_REFERENCE, DATA_VERIFIED, FeatureValue

_FORBIDDEN = ("truth_id", "truth")
_REQUIRED = (
    "sensor_id",
    "modality",
    "tick",
    "azimuth_deg",
    "elevation_deg",
    "sigma_azimuth_deg",
    "sigma_elevation_deg",
)


class MeasurementError(ValueError):
    """A report the tracker cannot use, or one that carries ground truth."""


@dataclass(frozen=True, slots=True)
class Measurement:
    sensor_id: str
    modality: str
    tick: int
    azimuth_deg: float
    elevation_deg: float
    sigma_azimuth_deg: float
    sigma_elevation_deg: float
    range_m: float | None = None
    radial_speed_mps: float | None = None
    sigma_range_m: float | None = None
    sigma_radial_mps: float | None = None
    reported_class: str | None = None
    features: Mapping[str, FeatureValue] = field(default_factory=dict)
    data_status: str = DATA_REFERENCE
    #: Opaque sequence number the caller assigns, so a report can be found again later (for
    #: example one held for triangulation). It says nothing about the target. -1 when unused.
    ref: int = -1

    @property
    def has_range(self) -> bool:
        return self.range_m is not None and self.sigma_range_m is not None

    @classmethod
    def from_view(cls, view: Mapping[str, Any], ref: int = -1) -> "Measurement":
        """Build from `Detection.trainee_view()`; refuses anything that names the true target."""
        leaked = [k for k in view if k in _FORBIDDEN]
        if leaked:
            raise MeasurementError(f"a tracker input must not carry {', '.join(leaked)}")
        missing = [k for k in _REQUIRED if view.get(k) is None]
        if missing:
            raise MeasurementError(f"a report is missing {', '.join(missing)}")
        status = view.get("data_status", DATA_REFERENCE)
        if status not in (DATA_REFERENCE, DATA_VERIFIED):
            raise MeasurementError(f"unknown data_status {status!r}")
        return cls(
            sensor_id=str(view["sensor_id"]),
            modality=str(view["modality"]),
            tick=int(view["tick"]),
            azimuth_deg=float(view["azimuth_deg"]),
            elevation_deg=float(view["elevation_deg"]),
            sigma_azimuth_deg=float(view["sigma_azimuth_deg"]),
            sigma_elevation_deg=float(view["sigma_elevation_deg"]),
            range_m=_opt(view.get("range_m")),
            radial_speed_mps=_opt(view.get("radial_speed_mps")),
            sigma_range_m=_opt(view.get("sigma_range_m")),
            sigma_radial_mps=_opt(view.get("sigma_radial_mps")),
            reported_class=view.get("reported_class"),
            features=dict(view.get("features") or {}),
            data_status=str(status),
            ref=ref,
        )

    def to_state(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "Measurement":
        return cls(**state)


def _opt(value: Any) -> float | None:
    return None if value is None else float(value)
