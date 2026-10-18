"""Shared fixtures for the RF and acoustic model tests: shipped profiles, scenes, observations.

Importing the two model modules registers them in the global model table. Other tests (the
framework's registration test among them) assume the `rf` and `acoustic` slots are free until the
package imports the models, so the table is put back; tests here pass `models=` explicitly.
"""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from app.contracts import SensorProfile
from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import ScenarioSpec, SensorPlacement
from sim.sensors import Environment, Geometry, Observation, SensorParams, Truth, suite
from sim.sensors.degradation import Effects
from sim.sensors.detection import Draws
from sim.sensors.geometry import truths
from sim.world import World

from .sim_cases import kestrel

_registered = dict(suite.MODELS)
from sim.sensors.acoustic import AcousticSensor  # noqa: E402
from sim.sensors.rf import RfSensor  # noqa: E402

suite.MODELS.clear()
suite.MODELS.update(_registered)

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs" / "DATA_REGISTER.md"
PROFILE_DIR = REPO / "packs" / "sensor-profiles"
RF_FILE = PROFILE_DIR / "rf-generic-passive.v1.yaml"
ACOUSTIC_FILE = PROFILE_DIR / "acoustic-generic-array.v1.yaml"

#: Draws that make every roll succeed (detect = 0) and give zero noise.
LUCKY = Draws(0.0, 0.0, (0.0, 0.0, 0.0, 0.0))
#: Draws that make every roll fail (detect just under 1) and give zero noise.
UNLUCKY = Draws(0.999999, 0.5, (0.0, 0.0, 0.0, 0.0))
SENSOR_ID = "s-1"

__all__ = ["AcousticSensor", "RfSensor"]


def q(value: float, unit: str, source: str = "F01") -> dict[str, Any]:
    return {"value": value, "unit": unit, "source_id": source, "verified": False}


def profile_data(path: Path, **overrides: dict[str, Any] | None) -> dict[str, Any]:
    """A shipped profile as a dict; `name=None` removes a parameter, `name=q(...)` replaces one."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, value in overrides.items():
        if value is None:
            data["parameters"].pop(name)
        else:
            data["parameters"][name] = value
    return copy.deepcopy(data)


def params_from(data: dict[str, Any]) -> SensorParams:
    return SensorParams(SensorProfile.model_validate(data))


def params(path: Path, **overrides: dict[str, Any] | None) -> SensorParams:
    return params_from(profile_data(path, **overrides))


def placement(p: SensorParams, position: Vec3, sensor_id: str = SENSOR_ID) -> SensorPlacement:
    return SensorPlacement(
        id=sensor_id,
        profile=PackRef(id=p.id, version=p.version),
        position=position,
        boresight_deg=0.0,
    )


def build[S](
    cls: Callable[[SensorPlacement, SensorParams], S],
    path: Path,
    position: Vec3 | None = None,
    **over: dict[str, Any] | None,
) -> S:
    p = params(path, **over)
    return cls(placement(p, position or Vec3(x=0, y=0, z=6)), p)


def env(
    *,
    wind: float = 2.0,
    condition: str = "clear",
    hour: float = 12.0,
    daylight: float = 1.0,
    visibility: float = 20_000.0,
    temperature: float = 20.0,
    cloud: float = 20.0,
) -> Environment:
    return Environment(condition, visibility, wind, temperature, cloud, hour, daylight)


def truth_at(range_m: float, class_id: str = "rotary-small", z: float = 30.0) -> Truth:
    """A stationary target `range_m` due north of the origin in the horizontal plane (plus height)."""
    return Truth("t-1", class_id, 0.0, range_m, z, 0.0, 0.0, 0.0)


def observe(
    sensor: Any,
    class_id: str,
    range_m: float,
    *,
    environment: Environment | None = None,
    effects: Effects | None = None,
    draws: Draws = LUCKY,
    z: float = 30.0,
) -> Observation:
    """A hand-built observation at (approximately) the given slant range from the sensor."""
    target = truth_at(range_m, class_id, z)
    return Observation(
        0,
        target,
        Geometry.between(sensor.position, target),
        environment or env(),
        effects or Effects(),
        draws,
    )


def with_classes(spec: ScenarioSpec, *class_ids: str) -> ScenarioSpec:
    """The Kestrel scenario with its threats relabelled to these classes (one per threat)."""
    threats = [
        t.model_copy(update={"class_id": c}) for t, c in zip(spec.threats, class_ids, strict=False)
    ]
    return spec.model_copy(update={"threats": threats})


def scene(class_id: str = "rotary-small", seed: int = 7, tick: int = 200) -> tuple[World, Truth]:
    """The Kestrel world, first contact relabelled to `class_id` and already flying."""
    spec = with_classes(kestrel(), class_id, "fixed-wing-small")
    world = World(spec, seed)
    while world.tick < tick:
        world.step()
    return world, truths(world)[0]


def south_of(target: Truth, distance: float, z: float = 6.0) -> Vec3:
    """A position `distance` m due south of the target, so the target bears 0 (north)."""
    return Vec3(x=target.x, y=target.y - distance, z=z)
