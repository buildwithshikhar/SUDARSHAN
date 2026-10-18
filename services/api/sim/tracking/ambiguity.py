"""The seeded association-error policy: a tracker that gets confused the way real ones do.

A track can only be confused where it has company. The tracker calls the policy for *ambiguous*
components only (two tracks inside each other's gates, or two reports inside one gate). An
unambiguous component, one track and one report, is returned unchanged; a test pins that no error
mode can apply to it. So two targets that stay apart never produce an error, and the chance of an
error grows as targets cross and as clutter plots appear in a gate.

For a component and the one uniform `draw` in [0, 1) the tracker supplies, the unit interval is
cut into consecutive intervals, in this order: swap, split, merge, nominal. A mode that does not
apply to the component has probability 0 and takes no interval. Let `c` be the normalised
innovation squared of a gated pair (the association cost), `N` the nominal nearest-neighbour
assignment, and `k = swap_scale`.

swap (two tracks exchange reports)
    Applies if the component has at least two tracks and two reports, and there is a complete
    alternative pairing with the same number of pairs as `N`, every pair inside the gate. The
    cheapest such alternative `A` is used (ties: by track id, then report index).
    `p_swap = swap_max * exp(-max(0, cost(A) - cost(N)) / k)`, cost being the sum of pair costs.
    The closer the alternative is to the nominal in cost, the likelier the mix-up.

split (a gated report starts a second track)
    Applies if at least one report of the component is left unpaired by `N`. The leftover report
    with the cheapest gated pair is the one that spawns a tentative track; `N` is still applied.
    With `n` leftover reports, `p_split = split_max * (1 - exp(-clutter_gain * n))`: more plots
    in the gate, more splits.

merge (one track loses its report, so two targets are treated as one)
    Applies if `N` has at least two pairs. The nominal pair with the highest cost (ties: the
    larger track id) is dropped, so that track gets no report this tick and its report is
    discarded. `p_merge = merge_max * exp(-c_d / k)` with `c_d` the cost of the dropped pair.
    A track that is repeatedly starved goes on coasting, and the tracker folds two tracks that
    end up on top of one another into one.

Defaults are project-authored fictional values (register ID F01, verified: false); see
docs/SENSOR_MODELS.md. The sum of the three maxima must not exceed 1, so the intervals fit in
[0, 1). The exponential is `sim.detmath.exp`, and costs are summed in sorted order, so the result
is bit-identical on every platform. The policy holds no state: the same component and draw always
give the same resolution.
"""

from dataclasses import asdict, dataclass, replace
from typing import Any

from .. import detmath
from .associate import Component, Pair, Resolution

#: Largest component (tracks or reports) searched for a swap; beyond it a swap is not offered.
MAX_SWAP_SIDE = 8


@dataclass(frozen=True, slots=True)
class ErrorModel:
    #: Largest probability of a swap (cost of the alternative equal to the nominal).
    swap_max: float = 0.5
    #: Cost scale of the swap and merge probabilities, in association-cost (NIS) units.
    swap_scale: float = 4.0
    #: Largest probability of a split.
    split_max: float = 0.15
    #: Largest probability of a merge.
    merge_max: float = 0.15
    #: How fast the split probability rises with each extra plot in the gate, per plot.
    clutter_gain: float = 0.5
    #: Multiplier on all three error probabilities; 1.0 is the default behaviour, above 1 errs more.
    difficulty: float = 1.0

    def __post_init__(self) -> None:
        for name in ("swap_max", "split_max", "merge_max"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} is a probability, got {value}")
        if not self.swap_scale > 0.0:
            raise ValueError(f"swap_scale must be positive, got {self.swap_scale}")
        if self.clutter_gain < 0.0:
            raise ValueError(f"clutter_gain cannot be negative, got {self.clutter_gain}")
        if not self.difficulty >= 0.0:
            raise ValueError(f"difficulty cannot be negative, got {self.difficulty}")
        if self.swap_max + self.split_max + self.merge_max > 1.0:
            raise ValueError(
                "the largest swap, split and merge probabilities must sum to 1 or less"
            )

    def to_state(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Option:
    """One error mode that applies to a component, with its probability and what it would do."""

    mode: str
    probability: float
    resolution: Resolution


class ErrorPolicy:
    """`AmbiguityPolicy` that errs with the probabilities of an `ErrorModel`."""

    def __init__(self, model: ErrorModel | None = None) -> None:
        self.model = model or ErrorModel()

    def options(self, component: Component) -> list[Option]:
        """Every error mode that applies to the component, in interval order (swap, split, merge).

        Empty for an unambiguous component: structurally, nothing there can go wrong.
        """
        if not component.ambiguous:
            return []
        out: list[Option] = []
        for build in (self._swap, self._split, self._merge):
            option = build(component)
            if option is not None and option.probability > 0.0:
                out.append(option)
        return self._scaled(out)

    def _scaled(self, options: list[Option]) -> list[Option]:
        """Apply `difficulty`; if that pushes the total above 1, shrink all in proportion."""
        factor = self.model.difficulty
        if factor == 1.0:
            return options
        scaled = [replace(o, probability=o.probability * factor) for o in options]
        total = 0.0
        for option in scaled:
            total += option.probability
        if total > 1.0:
            scaled = [replace(o, probability=o.probability / total) for o in scaled]
        return [o for o in scaled if o.probability > 0.0]

    def resolve(self, component: Component, draw: float) -> Resolution:
        nominal = Resolution("nominal", tuple((p.track, p.index) for p in component.nominal))
        edge = 0.0
        for option in self.options(component):
            edge += option.probability
            if draw < edge:
                return option.resolution
        return nominal

    # ------------------------------------------------------------------ the modes

    def _swap(self, component: Component) -> Option | None:
        if len(component.tracks) < 2 or len(component.measurements) < 2:
            return None
        if len(component.tracks) > MAX_SWAP_SIDE or len(component.measurements) > MAX_SWAP_SIDE:
            return None
        nominal = sorted((p.track, p.index) for p in component.nominal)
        best: tuple[float, list[tuple[str, int]], tuple[Pair, ...]] | None = None
        for pairing in _pairings(component, len(nominal)):
            key = sorted((p.track, p.index) for p in pairing)
            if key == nominal:
                continue
            cost = _total(sorted(pairing, key=lambda p: (p.track, p.index)))
            if best is None or (cost, key) < (best[0], best[1]):
                best = (cost, key, pairing)
        if best is None:
            return None
        excess = max(0.0, best[0] - _total(sorted(component.nominal, key=lambda p: p.track)))
        p = self.model.swap_max * detmath.exp(-excess / self.model.swap_scale)
        return Option("swap", p, Resolution("swap", tuple((q.track, q.index) for q in best[2])))

    def _split(self, component: Component) -> Option | None:
        used = {p.index for p in component.nominal}
        leftover = [i for i in component.measurements if i not in used]
        if not leftover:
            return None
        spawn = next(p.index for p in component.pairs if p.index not in used)
        p = self.model.split_max * (1.0 - detmath.exp(-self.model.clutter_gain * len(leftover)))
        nominal = tuple((q.track, q.index) for q in component.nominal)
        return Option("split", p, Resolution("split", nominal, spawn=(spawn,)))

    def _merge(self, component: Component) -> Option | None:
        if len(component.nominal) < 2:
            return None
        dropped = max(component.nominal, key=lambda q: (q.cost, q.track))
        p = self.model.merge_max * detmath.exp(-dropped.cost / self.model.swap_scale)
        kept = tuple((q.track, q.index) for q in component.nominal if q is not dropped)
        return Option("merge", p, Resolution("merge", kept))


def _total(pairs: list[Pair]) -> float:
    total = 0.0
    for pair in pairs:
        total += pair.cost
    return total


def _pairings(component: Component, size: int) -> list[tuple[Pair, ...]]:
    """Every set of `size` gated pairs with no track and no report used twice."""
    by_track: dict[str, list[Pair]] = {t: [] for t in component.tracks}
    for pair in component.pairs:
        by_track[pair.track].append(pair)
    tracks = component.tracks
    found: list[tuple[Pair, ...]] = []

    def walk(at: int, chosen: list[Pair], taken: set[int]) -> None:
        if len(chosen) == size:
            found.append(tuple(chosen))
            return
        if len(chosen) + (len(tracks) - at) < size:
            return
        for pair in by_track[tracks[at]]:
            if pair.index not in taken:
                chosen.append(pair)
                taken.add(pair.index)
                walk(at + 1, chosen, taken)
                taken.remove(pair.index)
                chosen.pop()
        walk(at + 1, chosen, taken)

    walk(0, [], set())
    return found
