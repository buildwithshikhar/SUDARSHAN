"""Proof that the sim core and the packs are present and work in this process or image.

`python -m app.cli sim-check` runs it. `make prod-check` runs it inside the production API
container, so an image built without `sim/` or `packs/` fails (Q-19).
"""

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root


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
    return f"sim ok: {spec.id} {ticks} ticks, {len(record.events)} events, packs at {root}"
