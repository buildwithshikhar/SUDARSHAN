"""Shared cases for the tracker error, ledger, command and cue tests.

`Crossing` runs the rig with the truth ledger beside it; the ledger gets ground truth only through
its own argument, never through the tracker. `Feed` builds tracker updates by hand so the ledger
can be tested without a world.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contracts import ScenarioSpec
from app.contracts.common import Vec3
from sim.tracking import AmbiguityPolicy, Association, TrackEvent, UpdateResult
from sim.tracking.ambiguity import ErrorPolicy
from sim.tracking.associate import Component, Pair, components
from sim.tracking.ledger import LedgerEvent, TruthLedger

from .tracking_rig import Rig, drone, radar_params, scenario, sensor

#: The documented swap: with `ErrorPolicy()` at its defaults, two rotary-small drones crossing
#: (see `crossing`) and this seed, track T001 and T002 exchange drones and the ledger records it at
#: this tick. The default policy and the nominal one differ here: with the nominal policy this seed
#: gives no swap.
SWAP_SEED = 47
SWAP_TICK = 648
RADAR = Vec3(x=0, y=0, z=6)


def crossing_threats() -> list[dict[str, Any]]:
    """Alpha east and bravo west at 15 m/s, passing each other 1500 m north of the radar."""
    return [
        drone("alpha", "rotary-small", (-450, 1500, 150), 90, 15, [(450, 1500, 150)]),
        drone("bravo", "rotary-small", (450, 1500, 150), 270, 15, [(-450, 1500, 150)]),
    ]


def parallel_threats(apart_m: float) -> list[dict[str, Any]]:
    """Two drones flying north at 15 m/s on lines `apart_m` apart in cross-range, same range."""
    half = apart_m / 2.0
    return [
        drone("alpha", "rotary-small", (-half, 300, 150), 0, 15, [(-half, 1100, 150)]),
        drone("bravo", "rotary-small", (half, 300, 150), 0, 15, [(half, 1100, 150)]),
    ]


def formation_threats(gap_m: float) -> list[dict[str, Any]]:
    """Two drones flying east side by side `gap_m` apart: ambiguous for the whole flight."""
    return [
        drone("alpha", "rotary-small", (-450, 1500, 150), 90, 15, [(450, 1500, 150)]),
        drone(
            "bravo", "rotary-small", (-450, 1500 + gap_m, 150), 90, 15, [(450, 1500 + gap_m, 150)]
        ),
    ]


@dataclass
class Crossing:
    """A rig with a radar at (0, 0, 6), a policy and a truth ledger fed beside the tracker."""

    rig: Rig
    ledger: TruthLedger
    events: list[tuple[int, LedgerEvent]] = field(default_factory=list)

    def run_to(self, tick: int) -> None:
        while self.rig.world.tick < tick:
            self.rig.step()
            at, result = self.rig.history[-1]
            for e in self.ledger.observe(at, result, self.rig.truth):
                self.events.append((at, e))

    def kinds(self) -> list[tuple[int, str]]:
        return [(t, e.kind) for t, e in self.events]

    def modes(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for _, result in self.rig.history:
            for a in result.ambiguities:
                found[a.mode] = found.get(a.mode, 0) + 1
        return dict(sorted(found.items()))


def crossing(
    seed: int,
    policy: AmbiguityPolicy | None = None,
    *,
    threats: list[dict[str, Any]] | None = None,
    spec: ScenarioSpec | None = None,
    ticks: int = 0,
) -> Crossing:
    """A run of `ticks` ticks; pass a prebuilt `spec` to skip validating the scenario again."""
    rig = Rig(
        spec or scenario(threats if threats is not None else crossing_threats()),
        seed,
        [sensor("radar-1", radar_params(), RADAR)],
        policy=policy if policy is not None else ErrorPolicy(),
    )
    run = Crossing(rig, TruthLedger())
    run.run_to(ticks)
    return run


def component(*pairs: tuple[str, int, float]) -> Component:
    """One component from (track, report index, cost) gated pairs; they must be connected."""
    found = components("radar-1", [Pair(t, i, c) for t, i, c in pairs])
    assert len(found) == 1
    return found[0]


def confirm(track: str, tick: int = 0) -> TrackEvent:
    return TrackEvent("confirm", track, tick, {"track": track, "hits": 3})


def drop_event(
    track: str, reason: str = "lost", merged_into: str | None = None, tick: int = 0
) -> TrackEvent:
    payload: dict[str, Any] = {"track": track, "reason": reason, "age_s": 1.0}
    if merged_into is not None:
        payload["merged_into"] = merged_into
    return TrackEvent("drop", track, tick, payload)


class Feed:
    """Hand-built tracker updates: each `step` gives tracks reports and says who caused them."""

    def __init__(self) -> None:
        self.ledger = TruthLedger()
        self.truth: dict[int, str | None] = {}
        self.tick = 0
        self._ref = 0

    def step(
        self,
        reports: Mapping[str, Sequence[str | None]] | None = None,
        events: Sequence[TrackEvent] = (),
    ) -> list[LedgerEvent]:
        associations: list[Association] = []
        for track, causes in (reports or {}).items():
            for cause in causes:
                associations.append(Association(track, self._ref, "radar-1"))
                self.truth[self._ref] = cause
                self._ref += 1
        result = UpdateResult(events=list(events), associations=associations)
        out = self.ledger.observe(self.tick, result, self.truth)
        self.tick += 1
        return out

    def run(self, ticks: int, reports: Mapping[str, Sequence[str | None]]) -> list[LedgerEvent]:
        out: list[LedgerEvent] = []
        for _ in range(ticks):
            out.extend(self.step(reports))
        return out

    def start(self, **drones: str) -> None:
        """Birth and confirm one track per keyword, each following the named drone."""
        for track, cause in drones.items():
            self.step({track: [cause]}, [TrackEvent("init", track, self.tick, {"track": track})])
        self.run(3, {t: [c] for t, c in drones.items()})
        self.step({}, [confirm(t) for t in drones])
