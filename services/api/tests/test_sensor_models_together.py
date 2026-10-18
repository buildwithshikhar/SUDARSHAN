"""All shipped models run together: the Kestrel scenario with one sensor of each kind."""

from typing import Any

from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import SensorPlacement
from sim.sensors import SensorSuite, build_sensors, register_ids
from sim.world import World

from .sim_cases import REPO, kestrel

PROFILES = (
    ("radar-1", "radar-generic-s", "0.2.0"),
    ("eo-1", "eo-generic-day", "0.1.0"),
    ("nv-1", "eo-generic-nv", "0.1.0"),
    ("ir-1", "ir-generic-thermal", "0.1.0"),
    ("rf-1", "rf-generic-passive", "1.0.0"),
    ("ac-1", "acoustic-generic-array", "1.0.0"),
)


def suite_and_world(seed: int = 11) -> tuple[SensorSuite, World]:
    spec = kestrel()
    sensors = [
        SensorPlacement(
            id=sensor_id,
            profile=PackRef(id=profile, version=version),
            position=Vec3(x=-140.0 + 20.0 * i, y=85.0, z=6.0),
            boresight_deg=45.0,
        )
        for i, (sensor_id, profile, version) in enumerate(PROFILES)
    ]
    spec = spec.model_copy(update={"sensors": sensors})
    register = register_ids(REPO / "docs" / "DATA_REGISTER.md")
    return build_sensors(spec, register=register), World(spec, seed)


def run(seed: int = 11, ticks: int = 2400) -> list[dict[str, Any]]:
    suite, world = suite_and_world(seed)
    out: list[dict[str, Any]] = []
    for _ in range(ticks):
        out.extend(d.payload() for d in suite.detect(world))
        world.step()
    return out


def test_every_shipped_profile_builds_and_loads_against_the_register() -> None:
    suite, _ = suite_and_world()
    assert [s.id for s in suite.sensors] == [p[0] for p in PROFILES]


def test_a_scenario_run_through_all_models_repeats_exactly() -> None:
    first = run()
    assert first == run()
    assert {d["modality"] for d in first} >= {"radar", "rf"}
    assert first != run(seed=12)
