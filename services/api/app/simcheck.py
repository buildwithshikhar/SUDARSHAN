"""Proof that the sim core and the packs are present and work in this process or image.

`python -m app.cli sim-check` runs it. `make prod-check` runs it inside the production API
container, so an image built without `sim/` or `packs/` fails (Q-19).
"""

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import PackTerrain


def run_sim_check(ticks: int = 40) -> str:
    from sim import replay  # imported here so a missing package is reported by this check
    from sim.catalogue import load_catalogue, profile_problems
    from sim.sensors import load_sensor_profile

    root = packs_root()
    scenarios = sorted((root / "scenarios").glob("*.v1.json"))
    if not scenarios:
        raise FileNotFoundError(f"no scenario packs under {root / 'scenarios'}")
    spec = load_pack(scenarios[0])
    if not isinstance(spec, ScenarioSpec):
        raise TypeError(f"{scenarios[0].name} is not a scenario pack")
    _, record = replay.run(spec, 1, [], ticks, picture=True)
    # Every scenario on a terrain pack must load that pack (its hash is verified on load), so an
    # image built without `packs/terrain/` fails here and not in front of a trainee.
    # The threat catalogue must load, every scenario must use only its classes and limits, and every
    # sensor profile must cover every class (Q-21), so a pack set that drifts apart fails here.
    catalogue = load_catalogue()
    problems: list[str] = []
    on_packs: list[str] = []
    for path in scenarios:
        other = load_pack(path)
        if not isinstance(other, ScenarioSpec):
            raise TypeError(f"{path.name} is not a scenario pack")
        problems += [f"{path.name}: {p}" for p in catalogue.check_scenario(other)]
        if isinstance(other.world.terrain, PackTerrain):
            replay.run(other, 1, [], min(ticks, 20), picture=True)
            on_packs.append(other.world.terrain.id)
    profiles = [
        load_sensor_profile(path) for path in sorted((root / "sensor-profiles").glob("*.yaml"))
    ]
    problems += profile_problems(catalogue, profiles)
    if problems:
        raise ValueError("threat catalogue check failed: " + "; ".join(problems))
    terrain = f", terrain {', '.join(sorted(set(on_packs)))}" if on_packs else ""
    return (
        f"sim ok: {spec.id} {ticks} ticks, {len(record.events)} events{terrain}, "
        f"{len(catalogue)} threat classes, packs at {root}"
    )
