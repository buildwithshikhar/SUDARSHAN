"""Cueing: pointing a sensor at where something is expected.

Wave 4b wires cues to tracks. Here a cue is a request to slew the sensor to a bearing and
elevation, optionally with a narrower field of view. Slewing is rate-limited by the profile's
`slew_rate`; changing the field of view is immediate (a zoom, not a mechanical move). A cue holds
for `cue_hold` seconds (or `DEFAULT_CUE_HOLD_S`), then the sensor returns to its home pointing.
"""

from dataclasses import dataclass
from typing import Literal

#: How long a cue holds when the profile gives no `cue_hold`. A framework constant (F01).
DEFAULT_CUE_HOLD_S = 10.0


@dataclass(frozen=True, slots=True)
class CueRequest:
    sensor_id: str
    #: Compass bearing to point at.
    bearing_deg: float
    elevation_deg: float = 0.0
    #: "slew" keeps the current field of view; "narrow" also tightens it.
    kind: Literal["slew", "narrow"] = "slew"
    #: Requested field width for "narrow"; clamped to the sensor's range. Default: its narrowest.
    fov_deg: float | None = None


@dataclass(frozen=True, slots=True)
class Pointing:
    azimuth_deg: float
    elevation_deg: float
    #: Full angular width of the field of view; `None` for a sensor with no pointed field.
    fov_deg: float | None


@dataclass(frozen=True, slots=True)
class CueResult:
    accepted: bool
    reason: str | None = None
    #: Where the sensor will end up pointing, with its field of view.
    target: Pointing | None = None
