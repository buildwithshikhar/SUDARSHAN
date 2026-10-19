"""The communication graph of a group.

Two members within `link_range_m` are linked unless the pair's keyed draw for the current link
epoch is below `link_loss`. The link set is rebuilt only at an epoch boundary and kept until the
next one, so the cost is hash draws per epoch, not per tick. Consensus over a graph with failing
links is the model basis (Olfati-Saber, Fax and Murray); the link range and loss are fictional,
project-authored values.
"""

import math
from collections.abc import Callable, Sequence

Pair = tuple[str, str]


def pair_of(a: str, b: str) -> Pair:
    """The pair in canonical order (the smaller ID first)."""
    return (a, b) if a < b else (b, a)


def rebuild(
    ids: Sequence[str],
    xs: Sequence[float],
    ys: Sequence[float],
    link_range: float,
    link_loss: float,
    down_draw: Callable[[Pair], float],
) -> list[Pair]:
    """Links among the members at one epoch boundary, sorted. `down_draw(pair)` is the keyed
    uniform of that pair for the epoch; it is taken only for a pair in range, and not at all when
    the loss is 0 (every pair in range is up) or 1 (every pair is down)."""
    out: list[Pair] = []
    if link_loss >= 1.0:
        return out
    limit = link_range * link_range
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            dx, dy = xs[i] - xs[j], ys[i] - ys[j]
            if dx * dx + dy * dy > limit:
                continue
            pair = pair_of(ids[i], ids[j])
            if link_loss > 0.0 and down_draw(pair) < link_loss:
                continue
            out.append(pair)
    out.sort()
    return out


class Graph:
    """The links among the members that are still active."""

    def __init__(self, ids: Sequence[str], pairs: Sequence[Pair]) -> None:
        self.ids = list(ids)
        present = {i: True for i in ids}
        self._adj: dict[str, list[str]] = {i: [] for i in ids}
        for a, b in pairs:
            if a in present and b in present:
                self._adj[a].append(b)
                self._adj[b].append(a)
        for neighbours in self._adj.values():
            neighbours.sort()

    def neighbours(self, member: str) -> list[str]:
        return self._adj[member]

    def linked(self, a: str, b: str) -> bool:
        return b in self._adj[a]

    def components(self) -> list[list[str]]:
        """Connected components by union-find in a fixed order: each component lists its members
        in the order of `ids`, and the components are ordered by their first member."""
        parent = {i: i for i in self.ids}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a in self.ids:
            for b in self._adj[a]:
                ra, rb = find(a), find(b)
                if ra != rb:
                    # the root with the smaller ID wins, so the result never depends on the order
                    if ra < rb:
                        parent[rb] = ra
                    else:
                        parent[ra] = rb
        groups: dict[str, list[str]] = {}
        for i in self.ids:
            groups.setdefault(find(i), []).append(i)
        return [groups[r] for r in sorted(groups, key=self.ids.index)]


def component_count(ids: Sequence[str], pairs: Sequence[Pair]) -> int:
    return len(Graph(ids, pairs).components())


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = ax - bx, ay - by
    return math.sqrt(dx * dx + dy * dy)
