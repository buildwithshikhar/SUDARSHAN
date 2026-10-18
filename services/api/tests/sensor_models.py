"""Helpers for testing the radar and EO/IR models against their shipped profiles."""

import copy
from pathlib import Path
from typing import Any

import yaml

from app.contracts import SensorProfile
from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import SensorPlacement
from sim.sensors import (
    Draws,
    Effects,
    Environment,
    Geometry,
    Observation,
    Sensor,
    SensorParams,
    Truth,
    load_sensor_profile,
)

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs" / "DATA_REGISTER.md"
PROFILE_DIR = REPO / "packs" / "sensor-profiles"
RADAR = "radar-generic-s.v1.yaml"
EO_DAY = "eo-generic-day.v1.yaml"
EO_NV = "eo-generic-nv.v1.yaml"
THERMAL = "ir-generic-thermal.v1.yaml"
CLASSES = ("rotary-small", "fixed-wing-small", "bird")


def shipped(name: str) -> SensorParams:
    return load_sensor_profile(PROFILE_DIR / name)


def raw(name: str) -> dict[str, Any]:
    data = yaml.safe_load((PROFILE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def params_with(name: str, **overrides: dict[str, Any] | float | None) -> SensorParams:
    """A shipped profile with parameters replaced (`name=value` keeps unit and source) or removed."""
    data = copy.deepcopy(raw(name))
    for key, value in overrides.items():
        if value is None:
            data["parameters"].pop(key)
        elif isinstance(value, dict):
            data["parameters"][key] = value
        else:
            data["parameters"][key]["value"] = value
    return SensorParams(SensorProfile.model_validate(data))


def placement(
    params: SensorParams, position: Vec3 | None = None, boresight: float = 0.0, sid: str = "s-1"
) -> SensorPlacement:
    return SensorPlacement(
        id=sid,
        profile=PackRef(id=params.id, version=params.version),
        position=position or Vec3(x=0, y=0, z=6),
        boresight_deg=boresight,
    )


def build[S: Sensor](cls: type[S], params: SensorParams, position: Vec3 | None = None) -> S:
    return cls(placement(params, position), params)


def environment(
    condition: str = "clear", visibility_m: float = 20000.0, daylight: float = 1.0
) -> Environment:
    return Environment(condition, visibility_m, 3.0, 15.0, 20.0, 12.0, daylight)


def observation(
    *,
    class_id: str = "rotary-small",
    slant_range_m: float = 1000.0,
    elevation_deg: float = 10.0,
    radial_speed_mps: float = -10.0,
    aspect_deg: float = 90.0,
    condition: str = "clear",
    visibility_m: float = 20000.0,
    daylight: float = 1.0,
    effects: Effects | None = None,
    draws: Draws | None = None,
    t: int = 0,
) -> Observation:
    """One hand-made sensor-versus-target situation, so a test changes exactly one thing."""
    truth = Truth("tgt", class_id, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    geometry = Geometry(
        ground_range_m=slant_range_m,
        slant_range_m=slant_range_m,
        azimuth_deg=45.0,
        elevation_deg=elevation_deg,
        radial_speed_mps=radial_speed_mps,
        ground_speed_mps=abs(radial_speed_mps),
        aspect_deg=aspect_deg,
    )
    return Observation(
        t,
        truth,
        geometry,
        environment(condition, visibility_m, daylight),
        effects or Effects(),
        draws or Draws(0.0, 0.5, (0.0, 0.0, 0.0, 0.0)),
    )


def sweep(start: float, stop: float, step: float) -> list[float]:
    out, x = [], start
    while x <= stop:
        out.append(x)
        x += step
    return out


def bisect(f: Any, low: float, high: float, target: float, rising: bool = False) -> float:
    """The argument in [low, high] where monotonic `f` crosses `target` (a test-side search)."""
    for _ in range(60):
        mid = (low + high) / 2.0
        if (f(mid) > target) != rising:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0
