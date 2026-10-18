"""Cue a sensor to a track: point it where the tracker thinks the target is.

The bearing comes from the track's estimate projected to the cue tick (`x + v dt`, with `dt` since
the track was last predicted), seen from the sensor's own position. A narrow cue asks for a field
of view of about three position sigmas either side, converted to an angle at the track's range;
the sensor clamps the request between its own wide and narrow fields, so a track the tracker is
unsure about gets a wide look and a well-converged one a tight look. A target the track has
drifted off will be missed: the cue points at the estimate, not at the truth.

Whether the cue is accepted is the sensor's decision, and its own reason is passed on: a radar
cannot be cued, a sensor in outage refuses, and so does an elevation outside its limits. Only
`sim.detmath` and `sqrt` are used, so the bearing is the same on every platform.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .. import detmath
from ..sensors import CueRequest, CueResult, SensorSuite
from . import kalman
from .tracker import Tracker

#: A narrow cue's field covers this many position sigmas either side of the estimate.
COVERAGE_SIGMAS = 3.0
_KEYS = frozenset({"sensor", "track", "narrow"})


@dataclass(frozen=True, slots=True)
class CueOutcome:
    ok: bool
    reason: str | None
    request: CueRequest | None
    result: CueResult | None
    #: JSON-only record for the event log and the picture.
    payload: dict[str, Any]


def _refuse(sensor_id: str, track_id: str, reason: str) -> CueOutcome:
    payload = {
        "sensor": sensor_id,
        "track": track_id,
        "bearing_deg": None,
        "elevation_deg": None,
        "fov_deg": None,
        "accepted": False,
        "reason": reason,
    }
    return CueOutcome(False, reason, None, None, payload)


def cue_for_track(
    tracker: Tracker,
    suite: SensorSuite,
    tick: int,
    sensor_id: str,
    track_id: str,
    *,
    narrow: bool = True,
) -> CueOutcome:
    origin = tracker.sensor_positions.get(sensor_id)
    if origin is None:
        return _refuse(sensor_id, track_id, f"no sensor {sensor_id!r}")
    track = tracker.tracks.get(track_id)
    if track is None:
        return _refuse(sensor_id, track_id, f"no live track {track_id!r}")
    dt = (tick - track.last_predict) / tracker.tick_hz
    dx = track.x[0] + track.x[3] * dt - origin.x
    dy = track.x[1] + track.x[4] * dt - origin.y
    dz = track.x[2] + track.x[5] * dt - origin.z
    horizontal = math.sqrt(dx * dx + dy * dy)
    bearing = detmath.wrap360(detmath.atan2(dx, dy) / detmath.DEG)
    elevation = detmath.atan2(dz, horizontal) / detmath.DEG
    fov: float | None = None
    if narrow:
        slant = max(math.sqrt(horizontal * horizontal + dz * dz), 1.0)
        reach = COVERAGE_SIGMAS * kalman.position_sigma(track.p) / slant
        fov = 2.0 * detmath.atan(reach) / detmath.DEG
    request = CueRequest(sensor_id, bearing, elevation, "narrow" if narrow else "slew", fov)
    result = suite.cue(request, tick)
    shown = fov if result.target is None else result.target.fov_deg
    payload = {
        "sensor": sensor_id,
        "track": track_id,
        "bearing_deg": round(bearing, 3),
        "elevation_deg": round(elevation, 3),
        "fov_deg": None if shown is None else round(shown, 3),
        "accepted": result.accepted,
        "reason": result.reason,
    }
    return CueOutcome(result.accepted, result.reason, request, result, payload)


def apply_cue(
    tracker: Tracker, suite: SensorSuite, tick: int, payload: Mapping[str, Any]
) -> CueOutcome:
    """The action "sensor-cue": payload keys `sensor`, `track` and optional `narrow` (default
    true). Never raises on bad input."""
    sensor, track, narrow = payload.get("sensor"), payload.get("track"), payload.get("narrow", True)
    unknown = sorted(str(k) for k in payload if k not in _KEYS)
    if unknown:
        return _refuse(str(sensor), str(track), f"unexpected field {unknown[0]!r}")
    if not isinstance(sensor, str) or not isinstance(track, str) or not isinstance(narrow, bool):
        return _refuse(
            str(sensor), str(track), "needs sensor (text), track (text) and optional narrow (bool)"
        )
    return cue_for_track(tracker, suite, tick, sensor, track, narrow=narrow)
