"""All the sensors of one scenario, run together.

The suite owns the order: sensors in scenario order, each sensor's targets in scenario order, so
the `sensors` random stream is consumed identically in every run. It does not write events or
talk to a transport; waves 4b and 5 do that.
"""

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.contracts.paths import packs_root
from app.contracts.scenario import ScenarioSpec

from .base import Sensor
from .cue import CueRequest, CueResult
from .degradation import Degradation
from .detection import Detection
from .profile import ProfileError, resolve_profile

if TYPE_CHECKING:
    from ..world import World

#: Sensor model classes by profile modality. Each model module registers itself with
#: `register_model` when imported.
MODELS: dict[str, type[Sensor]] = {}


def register_model(cls: type[Sensor]) -> type[Sensor]:
    """Class decorator: make `cls` the model for each of its `modalities`."""
    for modality in cls.modalities:
        if modality in MODELS:
            raise ValueError(f"a model is already registered for {modality!r}")
        MODELS[modality] = cls
    return cls


def default_profile_dir() -> Path:
    """`sensor-profiles/` under the packs root (a source checkout or the production image)."""
    return packs_root() / "sensor-profiles"


class SensorSuite:
    def __init__(self, sensors: Sequence[Sensor]) -> None:
        ids = [s.id for s in sensors]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate sensor id")
        self.sensors = list(sensors)
        self._by_id = {s.id: s for s in sensors}

    def __getitem__(self, sensor_id: str) -> Sensor:
        return self._by_id[sensor_id]

    def detect(self, world: "World") -> list[Detection]:
        """Every sensor's detections for the world's current tick."""
        found: list[Detection] = []
        for sensor in self.sensors:
            found.extend(sensor.detect(world, world.tick, world.rng))
        return found

    def cue(self, request: CueRequest, t: int) -> CueResult:
        sensor = self._by_id.get(request.sensor_id)
        if sensor is None:
            return CueResult(False, f"no sensor {request.sensor_id!r}")
        return sensor.cue(request, t)

    def inject(self, degradation: Degradation) -> None:
        sensor = self._by_id.get(degradation.sensor_id)
        if sensor is None:
            raise KeyError(f"no sensor {degradation.sensor_id!r}")
        sensor.inject(degradation)

    def state(self) -> dict[str, Any]:
        return {"sensors": [s.state() for s in self.sensors]}

    def restore(self, state: dict[str, Any]) -> None:
        saved = state["sensors"]
        if [s["id"] for s in saved] != [s.id for s in self.sensors]:
            raise ValueError("saved sensor state does not match this scenario's sensors")
        for sensor, s in zip(self.sensors, saved, strict=True):
            sensor.restore(s)


def build_sensors(
    spec: ScenarioSpec,
    profile_dir: Path | None = None,
    *,
    models: Mapping[str, type[Sensor]] | None = None,
    register: Collection[str] | None = None,
) -> SensorSuite:
    """Instantiate the scenario's sensors from their profiles and registered models.

    Fails before the session starts if a profile is missing or incomplete, no model exists for its
    modality, or a confusion table does not cover every threat class in the scenario.
    """
    available = MODELS if models is None else models
    directory = default_profile_dir() if profile_dir is None else profile_dir
    sensors: list[Sensor] = []
    for placement in spec.sensors:
        params = resolve_profile(placement.profile, directory, register=register)
        model = available.get(params.modality)
        if model is None:
            raise ProfileError(f"no sensor model for modality {params.modality!r}")
        sensor = model(placement, params)
        sensor.check_scenario(spec)
        sensors.append(sensor)
    return SensorSuite(sensors)
