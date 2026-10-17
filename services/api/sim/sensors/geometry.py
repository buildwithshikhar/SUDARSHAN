"""What a sensor can know about the world: truth snapshots, geometry and the environment.

Everything here uses only the operations allowed by `sim.detmath`, because detections reach the
event log and must be identical on every platform.
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.contracts import TICK_HZ
from app.contracts.common import Vec3

from .. import detmath

if TYPE_CHECKING:
    from ..world import World

#: Fictional fixed day length (no latitude is modelled): sunrise and sunset in scenario clock
#: hours, with a linear twilight of this width centred on each.
SUNRISE_H = 6.0
SUNSET_H = 18.0
TWILIGHT_H = 1.0

Phase = Literal["day", "twilight", "night"]


@dataclass(frozen=True, slots=True)
class Truth:
    """Ground truth of one active drone. Sensors read it; no trainee-facing view carries it."""

    id: str
    class_id: str
    x: float
    y: float
    z: float
    #: Ground velocity: air velocity plus wind.
    vx: float
    vy: float
    vz: float


def truths(world: "World") -> list[Truth]:
    """Active drones in scenario order."""
    wx, wy = world.wind()
    return [
        Truth(
            d.id,
            world.spec.threats[i].class_id,
            d.x,
            d.y,
            d.z,
            d.ux * d.airspeed + wx,
            d.uy * d.airspeed + wy,
            d.vz,
        )
        for i, d in enumerate(world.drones)
        if d.status == "active"
    ]


@dataclass(frozen=True, slots=True)
class Geometry:
    """The target as seen from a sensor position."""

    ground_range_m: float
    slant_range_m: float
    #: Compass bearing from the sensor to the target, [0, 360).
    azimuth_deg: float
    #: Angle above the horizontal plane through the sensor, [-90, 90].
    elevation_deg: float
    #: Rate of change of slant range; positive when the target is moving away.
    radial_speed_mps: float
    ground_speed_mps: float
    #: Angle between the target's velocity and the line from the target to the sensor:
    #: 0 head-on, 180 tail-on. 90 when the target is stationary.
    aspect_deg: float

    @classmethod
    def between(cls, origin: Vec3, t: Truth) -> "Geometry":
        dx, dy, dz = t.x - origin.x, t.y - origin.y, t.z - origin.z
        ground = math.sqrt(dx * dx + dy * dy)
        slant = math.sqrt(ground * ground + dz * dz)
        azimuth = detmath.wrap360(detmath.atan2(dx, dy) / detmath.DEG)
        elevation = detmath.atan2(dz, ground) / detmath.DEG
        speed = math.sqrt(t.vx * t.vx + t.vy * t.vy + t.vz * t.vz)
        along = (dx * t.vx + dy * t.vy + dz * t.vz) / slant if slant > 0.0 else 0.0
        if speed > 0.0:
            across = math.sqrt(max(speed * speed - along * along, 0.0))
            aspect = detmath.atan2(across, -along) / detmath.DEG
        else:
            aspect = 90.0
        return cls(
            ground,
            slant,
            azimuth,
            elevation,
            along,
            math.sqrt(t.vx * t.vx + t.vy * t.vy),
            aspect,
        )


@dataclass(frozen=True, slots=True)
class Environment:
    """Modelled conditions a detection model may use. Weather here is modelled, not measured."""

    condition: str
    visibility_m: float
    wind_speed_mps: float
    temperature_c: float
    cloud_cover_pct: float
    time_of_day_h: float
    #: 1 in full daylight, 0 at night, linear through twilight.
    daylight: float

    @property
    def phase(self) -> Phase:
        return "day" if self.daylight >= 1.0 else "night" if self.daylight <= 0.0 else "twilight"

    @classmethod
    def of(cls, world: "World", t: int) -> "Environment":
        w = world.weather
        wx, wy = world.wind()
        hour = (world.spec.world.start_time_of_day_h + t / TICK_HZ / 3600.0) % 24.0
        return cls(
            condition=w.condition,
            visibility_m=w.visibility_m,
            wind_speed_mps=math.sqrt(wx * wx + wy * wy),
            temperature_c=w.temperature_c,
            cloud_cover_pct=w.cloud_cover_pct,
            time_of_day_h=hour,
            daylight=daylight_at(hour),
        )


def daylight_at(hour: float) -> float:
    """Daylight fraction at a scenario clock hour, with a linear twilight at each end."""
    half = TWILIGHT_H / 2.0
    rising = (hour - (SUNRISE_H - half)) / TWILIGHT_H
    setting = ((SUNSET_H + half) - hour) / TWILIGHT_H
    return detmath.clamp(min(rising, setting), 0.0, 1.0)
