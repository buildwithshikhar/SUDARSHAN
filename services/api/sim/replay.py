"""Run a session from spec + seed + action log, and replay a recorded session.

A session record holds the inputs (scenario reference, seed, tick count, action log) and the
outputs (every event and the final state hash). Replaying re-runs the inputs and compares the
outputs event by event, so a divergence is reported at the first event that differs.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import groupby

from app.contracts import ActionRecord, ScenarioSpec, SessionRecord
from app.contracts.common import PackRef

from .tracking.picture import Picture
from .world import ActionError, World


def ordered(actions: Iterable[ActionRecord]) -> list[ActionRecord]:
    """Actions in tick order; ties keep their log order (Python's sort is stable)."""
    return sorted(actions, key=lambda a: a.tick)


def advance(world: World, until_tick: int, actions: Sequence[ActionRecord] = ()) -> World:
    """Step `world` up to (not including) `until_tick`, applying the actions for each tick."""
    pending = [a for a in ordered(actions) if a.tick >= world.tick]
    if any(a.tick >= until_tick for a in pending):
        raise ActionError(f"an action is scheduled at or after tick {until_tick}")
    by_tick = {tick: list(group) for tick, group in groupby(pending, key=lambda a: a.tick)}
    while world.tick < until_tick:
        world.step(by_tick.get(world.tick, ()))
    return world


def finish(world: World) -> str:
    """Close the log with a session.end event and return the final state hash."""
    final = world.state_hash()
    world.log.append(world.tick, "session.end", "sim", {"ticks": world.tick, "state_hash": final})
    return final


def run(
    spec: ScenarioSpec,
    seed: int,
    actions: Sequence[ActionRecord],
    ticks: int,
    *,
    picture: bool = False,
) -> tuple[World, SessionRecord]:
    """Run a session; `picture=True` attaches the sensors, tracker, ledger and assist (wave 4b)."""
    world = advance(
        World(spec, seed, picture=Picture.build(spec, seed) if picture else None), ticks, actions
    )
    final = finish(world)
    record = SessionRecord(
        contract="session-record.v1",
        scenario=PackRef(id=spec.id, version=spec.version),
        seed=seed,
        ticks=ticks,
        actions=ordered(actions),
        events=list(world.log.records),
        final_state_hash=final,
        picture=picture,
    )
    return world, record


@dataclass(frozen=True, slots=True)
class ReplayResult:
    matches: bool
    #: seq of the first event that differs (or is missing on one side), None when all match
    first_divergent_seq: int | None
    final_state_hash: str


def replay(spec: ScenarioSpec, record: SessionRecord) -> ReplayResult:
    """Re-run a record, with a sensor picture if the record says it had one."""
    if (record.scenario.id, record.scenario.version) != (spec.id, spec.version):
        raise ValueError("the session record is for a different scenario or version")
    _, again = run(spec, record.seed, record.actions, record.ticks, picture=record.picture)
    diverged = next(
        (i for i, (a, b) in enumerate(zip(record.events, again.events, strict=False)) if a != b),
        None,
    )
    if diverged is None and len(record.events) != len(again.events):
        diverged = min(len(record.events), len(again.events))
    matches = diverged is None and again.final_state_hash == record.final_state_hash
    return ReplayResult(matches, diverged, again.final_state_hash)
