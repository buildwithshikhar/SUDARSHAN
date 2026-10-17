"""Golden files pin sim behaviour for a fixed set of scenarios, seeds and action logs.

A failure prints a unified diff of the golden text. If the change is intended (a deliberate
physics or rule change), regenerate and commit the files, and say why in the commit:

    UPDATE_GOLDEN=1 uv run pytest tests/test_sim_golden.py
"""

import difflib
import os

import pytest

from app.contracts import ActionRecord
from sim.replay import advance, finish
from sim.world import World

from .sim_cases import GOLDEN_CASES, GOLDEN_DIR, kestrel

SAMPLE_EVERY = 200  # ticks (10 s)


def render(name: str, seed: int, ticks: int, actions: list[ActionRecord]) -> str:
    spec = kestrel()
    world = World(spec, seed)
    samples: list[str] = []
    while world.tick < ticks:
        until = min(world.tick + SAMPLE_EVERY, ticks)
        advance(world, until, [a for a in actions if world.tick <= a.tick < until])
        for d in world.drones:
            if d.status == "active":
                samples.append(
                    f"  t={world.time_s:7.2f} {d.id} {d.mode:6} leg={d.leg} "
                    f"x={d.x:10.3f} y={d.y:10.3f} z={d.z:8.3f} v={d.airspeed:6.3f} "
                    f"vz={d.vz:6.3f} heading=({d.ux:+.5f},{d.uy:+.5f})"
                )
        samples.append(
            f"  t={world.time_s:7.2f} wind gust=({world.weather.gust_x:+.4f},"
            f"{world.weather.gust_y:+.4f})"
        )
    final = finish(world)
    events = [
        f"  {r.seq:3} t={r.t:7.2f} {r.type} {r.actor} {r.payload.get('id', '')}".rstrip()
        for r in world.log.records
    ]
    return "\n".join(
        [
            f"# golden: {name} · scenario {spec.id} {spec.version} · seed {seed} · {ticks} ticks",
            "# regenerate on purpose: UPDATE_GOLDEN=1 uv run pytest tests/test_sim_golden.py",
            f"final_state_hash {final}",
            f"event_head {world.log.head}",
            "events",
            *events,
            f"samples (every {SAMPLE_EVERY} ticks)",
            *samples,
            "",
        ]
    )


def golden_diff(name: str, seed: int, ticks: int, actions: list[ActionRecord]) -> str:
    """Unified diff between the stored golden file and a fresh run ('' when they match)."""
    path = GOLDEN_DIR / f"{name}.txt"
    actual = render(name, seed, ticks, actions)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8")
    expected = path.read_text(encoding="utf-8") if path.exists() else ""
    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        f"golden/{name}.txt",
        "this run",
        n=1,
        lineterm="",
    )
    return "\n".join(diff)


@pytest.mark.parametrize(
    ("name", "seed", "ticks", "actions"), GOLDEN_CASES, ids=[c[0] for c in GOLDEN_CASES]
)
def test_sim_matches_its_golden_file(
    name: str, seed: int, ticks: int, actions: list[ActionRecord]
) -> None:
    diff = golden_diff(name, seed, ticks, actions)
    if diff:
        lines = diff.splitlines()
        shown = "\n".join(lines[:80]) + (
            f"\n... {len(lines) - 80} more lines" if len(lines) > 80 else ""
        )
        pytest.fail(f"sim behaviour changed for {name}:\n{shown}", pytrace=False)


@pytest.mark.parametrize(
    ("module", "constant", "value"),
    [
        ("sim.kinematics", "ORBIT_RADIUS_M", 150.0),
        ("sim.kinematics", "ARRIVAL_RADIUS_MIN_M", 25.0),
        ("sim.kinematics", "CLIMB_GAIN_PER_S", 0.6),
        ("sim.world", "GUST_TAU_S", 5.0),
    ],
)
def test_changing_a_physics_constant_fails_the_golden_files_with_a_readable_diff(
    monkeypatch: pytest.MonkeyPatch, module: str, constant: str, value: float
) -> None:
    monkeypatch.delenv("UPDATE_GOLDEN", raising=False)
    monkeypatch.setattr(f"{module}.{constant}", value)
    name, seed, ticks, actions = GOLDEN_CASES[0]
    diff = golden_diff(name, seed, ticks, actions)
    assert diff.startswith(f"--- golden/{name}.txt\n+++ this run")
    removed = [line for line in diff.splitlines() if line.startswith("-  t=")]
    added = [line for line in diff.splitlines() if line.startswith("+  t=")]
    assert removed and added  # the changed sample lines are shown side by side
    assert "-final_state_hash" in diff
