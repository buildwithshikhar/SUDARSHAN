"""Authoring helpers for scenario writers and the generator: when members arrive, what they are,
and where they start.

These are not run by the world. `spawn_s` on each member stays authoritative; the helpers only
compute numbers to put there. All are deterministic (keyed draws, no random stream).
"""

import math

from .. import detmath
from . import draws, leaderfollower

PROFILES = ("simultaneous", "staggered", "waves", "trickle")
DECOY_CLASS = "decoy-small"
SILENT_CLASS = "autonomous-small"


def arrival_offsets(profile: str, n: int, span_s: float, seed: int, waves: int = 3) -> list[float]:
    """Seconds after the first arrival at which each of `n` members spawns, in member order.

    simultaneous: all at 0. staggered: evenly spread over `span_s`. waves: `waves` bursts evenly
    spread over `span_s`, members shared out as equally as possible, earlier bursts getting the
    spare ones. trickle: independent keyed uniform times over `span_s`, sorted.
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown arrival profile {profile!r}; one of {', '.join(PROFILES)}")
    if n < 1 or span_s < 0:
        raise ValueError("n must be at least 1 and span_s not negative")
    if profile == "simultaneous" or n == 1:
        return [0.0] * n
    if profile == "staggered":
        return [i * span_s / (n - 1) for i in range(n)]
    if profile == "waves":
        bursts = min(max(waves, 1), n)
        out: list[float] = []
        for b in range(bursts):
            size = n // bursts + (1 if b < n % bursts else 0)
            when = 0.0 if bursts == 1 else b * span_s / (bursts - 1)
            out.extend([when] * size)
        return out
    return sorted(draws.uniform(seed, "arrival", str(i), 0, "trickle") * span_s for i in range(n))


def _rounded(x: float) -> int:
    return math.floor(x + 0.5)


def compose_members(
    base_class: str, n: int, decoy_fraction: float, silent_fraction: float, seed: int
) -> list[str]:
    """Class IDs for `n` members: `round(n * decoy_fraction)` decoys (`decoy-small`),
    `round(n * silent_fraction)` RF-silent autonomous drones (`autonomous-small`) and the rest
    `base_class`, placed by a keyed shuffle so the same seed gives the same list."""
    decoys, silent = _rounded(n * decoy_fraction), _rounded(n * silent_fraction)
    if not (0.0 <= decoy_fraction <= 1.0 and 0.0 <= silent_fraction <= 1.0):
        raise ValueError("fractions must be between 0 and 1")
    if decoys + silent > n:
        raise ValueError("the decoy and silent members together exceed the group")
    order = sorted(
        range(n), key=lambda i: (draws.uniform(seed, "compose", str(i), 0, "shuffle"), i)
    )
    out = [base_class] * n
    for rank, index in enumerate(order):
        if rank < decoys:
            out[index] = DECOY_CLASS
        elif rank < decoys + silent:
            out[index] = SILENT_CLASS
    return out


def formation_starts(
    n: int, spacing_m: float, centre: tuple[float, float], heading_deg: float, intent: str
) -> list[tuple[float, float]]:
    """Start positions for `n` members of a group about to fly along `heading_deg`: the leader's
    slot (member 0) at `centre`, the others in the formation the intent implies."""
    ux, uy = detmath.heading_vector(heading_deg)
    slots = leaderfollower.offsets(leaderfollower.formation_for(intent), n, spacing_m)
    return [leaderfollower.to_world(centre[0], centre[1], ux, uy, s) for s in slots]
