"""Gated nearest-neighbour association, grouped into components of competing candidates.

For one sensor's reports at one tick, every (track, report) pair whose normalised innovation lies
inside the gate is a candidate. Candidates that share a track or a report form a *component*. A
component with one track and one report is unambiguous and is simply updated. Anything bigger is
*ambiguous*: two tracks inside each other's gates, or two reports inside one gate (a second
target, a clutter plot). Only there can the tracker make an association error, and what it does
is decided by an `AmbiguityPolicy`. The default is the nominal nearest-neighbour assignment; the
seeded error policy lives in `ambiguity.py`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

Mode = Literal["nominal", "swap", "split", "merge"]


@dataclass(frozen=True, slots=True)
class Pair:
    track: str
    #: Index of the report in the list passed to `Tracker.update`.
    index: int
    #: Normalised innovation squared; smaller is a better fit.
    cost: float


@dataclass(frozen=True, slots=True)
class Component:
    sensor_id: str
    #: Track ids, sorted.
    tracks: tuple[str, ...]
    #: Report indices, ascending.
    measurements: tuple[int, ...]
    #: Every gated pair, sorted by (cost, track, index).
    pairs: tuple[Pair, ...]
    #: Greedy nearest-neighbour assignment: at most one report per track and one track per report.
    nominal: tuple[Pair, ...]

    @property
    def ambiguous(self) -> bool:
        return len(self.tracks) > 1 or len(self.measurements) > 1

    def cost(self, track: str, index: int) -> float | None:
        for pair in self.pairs:
            if pair.track == track and pair.index == index:
                return pair.cost
        return None


@dataclass(frozen=True, slots=True)
class Resolution:
    mode: Mode
    #: (track id, report index) to update. Each must be a gated pair of the component; no track
    #: and no report may appear twice.
    pairs: tuple[tuple[str, int], ...]
    #: Reports inside a gate that nevertheless start a new tentative track (a split).
    spawn: tuple[int, ...] = ()


class AmbiguityPolicy(Protocol):
    def resolve(self, component: Component, draw: float) -> Resolution:
        """Decide an ambiguous component. `draw` is one uniform in [0, 1) from the `tracking`
        stream, the one taken for the component's first report."""
        ...


class NominalPolicy:
    """Always the nearest-neighbour assignment: no association errors beyond what noise causes."""

    def resolve(self, component: Component, draw: float) -> Resolution:
        return Resolution("nominal", tuple((p.track, p.index) for p in component.nominal))


def greedy(pairs: Iterable[Pair]) -> tuple[Pair, ...]:
    """Nearest-neighbour assignment of already-sorted pairs."""
    used_tracks: set[str] = set()
    used_reports: set[int] = set()
    chosen: list[Pair] = []
    for pair in pairs:
        if pair.track in used_tracks or pair.index in used_reports:
            continue
        used_tracks.add(pair.track)
        used_reports.add(pair.index)
        chosen.append(pair)
    return tuple(chosen)


def components(sensor_id: str, gated: Sequence[Pair]) -> list[Component]:
    """Group gated pairs into components, ordered by their first report index."""
    parent: dict[tuple[str, object], tuple[str, object]] = {}

    def find(a: tuple[str, object]) -> tuple[str, object]:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for pair in gated:
        ra, rb = find(("t", pair.track)), find(("m", pair.index))
        if ra != rb:
            parent[rb] = ra
    groups: dict[tuple[str, object], list[Pair]] = {}
    for pair in gated:
        groups.setdefault(find(("t", pair.track)), []).append(pair)
    out: list[Component] = []
    for members in groups.values():
        ordered = tuple(sorted(members, key=lambda p: (p.cost, p.track, p.index)))
        out.append(
            Component(
                sensor_id=sensor_id,
                tracks=tuple(sorted({p.track for p in ordered})),
                measurements=tuple(sorted({p.index for p in ordered})),
                pairs=ordered,
                nominal=greedy(ordered),
            )
        )
    return sorted(out, key=lambda c: c.measurements[0])


def check(component: Component, resolution: Resolution) -> None:
    """Refuse a resolution that is not a valid reading of its component."""
    gated = {(p.track, p.index) for p in component.pairs}
    tracks = [t for t, _ in resolution.pairs]
    reports = [i for _, i in resolution.pairs]
    if len(set(tracks)) != len(tracks) or len(set(reports)) != len(reports):
        raise ValueError("a resolution assigns a track or a report twice")
    for pair in resolution.pairs:
        if pair not in gated:
            raise ValueError(f"resolution pairs {pair[0]} with report {pair[1]} outside the gate")
    for index in resolution.spawn:
        if index not in component.measurements or index in reports:
            raise ValueError(f"report {index} cannot start a track")
