"""A minimal sensor model and scene for testing the sensor framework in isolation.

`ToySensor` implements the two required methods with the simplest possible physics, so a test
failure points at the framework and not at a modality model.
"""

from typing import Any, ClassVar

from app.contracts import SensorProfile
from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import SensorPlacement
from sim.detmath import clamp
from sim.rng import RngStreams
from sim.sensors import (
    Detection,
    Effects,
    Environment,
    Observation,
    Sensor,
    SensorParams,
    Truth,
)
from sim.sensors.geometry import truths
from sim.world import World

from .sim_cases import kestrel

CLASSES = ("rotary-small", "fixed-wing-small")


def q(value: float, unit: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "source_id": "F01", "verified": False}


def profile_data(**overrides: dict[str, Any] | None) -> dict[str, Any]:
    """A complete toy profile; `name=None` removes a parameter, `name=q(...)` replaces one."""
    parameters = {
        "instrumented_range": q(5000, "m"),
        "update_interval": q(0.1, "s"),
        "sigma_range": q(10, "m"),
        "sigma_azimuth": q(1.0, "deg"),
        "sigma_elevation": q(0.5, "deg"),
        "fov_wide": q(60, "deg"),
        "fov_narrow": q(10, "deg"),
        "slew_rate": q(30, "deg/s"),
        "min_elevation": q(-5, "deg"),
        "max_elevation": q(60, "deg"),
    }
    for name, value in overrides.items():
        if value is None:
            parameters.pop(name)
        else:
            parameters[name] = value
    return {
        "contract": "sensor-profile.v1",
        "id": "toy-radar",
        "version": "1.0.0",
        "title": {"en": "Toy sensor", "hi": "परीक्षण सेंसर"},
        "modality": "radar",
        "fictional": True,
        "parameters": parameters,
        "confusion": {
            "default": {
                "labels": ["rotary-small", "fixed-wing-small", "unknown"],
                "rows": {
                    "rotary-small": [0.8, 0.1, 0.1],
                    "fixed-wing-small": [0.25, 0.5, 0.25],
                },
                "source_id": "F01",
                "verified": False,
            }
        },
    }


def toy_params(**overrides: dict[str, Any] | None) -> SensorParams:
    return SensorParams(SensorProfile.model_validate(profile_data(**overrides)))


class ToySensor(Sensor):
    modalities = ("radar",)
    supports_cue = True
    required_params = ("sigma_range", "sigma_azimuth", "sigma_elevation")
    confusion_keys = ("default",)
    #: Probability of detection used when set; otherwise linear in range.
    fixed_pd: ClassVar[float | None] = 1.0
    false_alarm_count: ClassVar[int] = 0

    def p_detect(self, obs: Observation) -> float:
        if self.fixed_pd is not None:
            return self.fixed_pd
        return clamp(1.0 - obs.geometry.slant_range_m / self.instrumented_range_m, 0.0, 1.0)

    def measure(self, obs: Observation) -> Detection:
        p = self.params
        return self.polar_detection(
            obs,
            sigma_range_m=p.value("sigma_range", "m"),
            sigma_azimuth_deg=p.value("sigma_azimuth", "deg"),
            sigma_elevation_deg=p.value("sigma_elevation", "deg"),
            reported_class=self.report_class(obs),
        )

    def degradation_effect(self, kind: str, severity: float) -> Effects | None:
        if kind == "haze":
            return Effects(pd_factor=1.0 - severity, noise_factor=1.0 + severity)
        if kind == "clutter":
            return Effects(clutter_factor=1.0 + 4.0 * severity)
        return None

    def precision_factor(self) -> float:
        fov, wide = self.pointing.fov_deg, self.params.value("fov_wide", "deg")
        return 1.0 if fov is None else fov / wide

    def false_alarms(
        self, world: World, t: int, rng: RngStreams, env: Environment, fx: Effects
    ) -> list[Detection]:
        found = []
        for _ in range(self.false_alarm_count):
            az, el = rng.uniform("sensors") * 360.0, rng.uniform("sensors") * 10.0
            found.append(Detection(self.id, "radar", t, None, az, el))
        return found


class AlwaysDetects(ToySensor):
    fixed_pd = 1.0


class NeverDetects(ToySensor):
    fixed_pd = 0.0


class LinearPd(ToySensor):
    fixed_pd = None


class NoisyAlarms(ToySensor):
    false_alarm_count = 2


class NoCueSensor(ToySensor):
    supports_cue = False


def placement(
    position: Vec3, boresight: float = 0.0, sensor_id: str = "toy-1", version: str = "1.0.0"
) -> SensorPlacement:
    return SensorPlacement(
        id=sensor_id,
        profile=PackRef(id="toy-radar", version=version),
        position=position,
        boresight_deg=boresight,
    )


def scene(seed: int = 7, tick: int = 200) -> tuple[World, Truth]:
    """The Kestrel world with its first contact flying, and that contact's truth."""
    world = World(kestrel(), seed)
    while world.tick < tick:
        world.step()
    return world, truths(world)[0]


def south_of(truth: Truth, distance: float = 1000.0, z: float = 6.0) -> Vec3:
    """A position `distance` m due south of the target, so the target bears 0 (north)."""
    return Vec3(x=truth.x, y=truth.y - distance, z=z)


def make(
    cls: type[ToySensor],
    truth: Truth,
    *,
    distance: float = 1000.0,
    boresight: float = 0.0,
    **over: Any,
) -> ToySensor:
    return cls(placement(south_of(truth, distance), boresight), toy_params(**over))
