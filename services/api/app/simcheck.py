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
    on_packs: list[str] = []
    for path in scenarios:
        other = load_pack(path)
        if isinstance(other, ScenarioSpec) and isinstance(other.world.terrain, PackTerrain):
            replay.run(other, 1, [], min(ticks, 20), picture=True)
            on_packs.append(other.world.terrain.id)
    terrain = f", terrain {', '.join(sorted(set(on_packs)))}" if on_packs else ""
    return f"sim ok: {spec.id} {ticks} ticks, {len(record.events)} events{terrain}, packs at {root}"
