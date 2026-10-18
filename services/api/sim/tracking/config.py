"""Tracker parameters. All are project-authored fictional values (register ID F01), not measured.

They are documented, with units and reasons, in docs/SENSOR_MODELS.md ("Tracking"); a test checks
that every field here appears in that section.
"""

from dataclasses import asdict, dataclass
from typing import Any

#: 99 % chi-square thresholds on the normalised innovation squared, by degrees of freedom.
CHI2_GATE: dict[int, float] = {1: 6.635, 2: 9.210, 3: 11.345, 4: 13.277}


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    #: Process noise: one-sigma acceleration of a manoeuvring small drone, m/s^2 (continuous white
    #: noise, so the result does not depend on how often the filter is stepped).
    accel_sigma_mps2: float = 2.0
    #: One-sigma speed uncertainty of a new track, m/s.
    init_speed_sigma_mps: float = 25.0
    #: Multiplies the chi-square gate thresholds; 1 is the 99 % gate.
    gate_scale: float = 1.0
    #: A report no track claimed starts a new track only if it lies outside this multiple of the
    #: gate around every confirmed or coasting track. Without it a lone target's gate-edge outlier
    #: would start a second track, which is a split the target's geometry did not cause.
    init_exclusion_scale: float = 2.5
    #: Floor on the angular measurement sigma, deg, so a very good sensor cannot make a gate vanish.
    min_sigma_angle_deg: float = 0.05
    #: Floor on the range measurement sigma, m.
    min_sigma_range_m: float = 1.0
    #: Fallback radial-speed sigma when a report does not give one, m/s.
    default_sigma_radial_mps: float = 1.0
    #: A tentative track is confirmed after this many ticks with an associated report ...
    confirm_hits: int = 3
    #: ... within this many seconds of its birth, otherwise it is dropped.
    confirm_window_s: float = 10.0
    #: A tentative track with no report for this long is dropped.
    tentative_drop_s: float = 4.0
    #: A confirmed track with no report for this long becomes coasting.
    coast_after_s: float = 3.0
    #: A coasting track with no report for this long is dropped.
    drop_after_s: float = 15.0
    #: Two confirmed tracks whose position and velocity estimates are statistically
    #: indistinguishable (squared distance over the summed variances below this, chi-square with
    #: 6 degrees of freedom at 95 %) for `duplicate_hold_s` are one track: the younger is dropped.
    #: If they were two targets, that is a merge error.
    duplicate_gate: float = 12.592
    duplicate_hold_s: float = 3.0
    #: Bearing-only reports with no track are held this long to be paired across sensors.
    triangulation_window_s: float = 0.5
    #: Rays closer than this angle are too parallel to triangulate, deg.
    triangulation_min_angle_deg: float = 8.0
    #: A pair of rays is accepted if they pass within this many one-sigma miss distances.
    triangulation_gate: float = 3.0
    #: Allowance for target motion between the two reports, m/s.
    triangulation_speed_mps: float = 30.0
    triangulation_max_range_m: float = 8000.0

    def to_state(self) -> dict[str, Any]:
        return asdict(self)
