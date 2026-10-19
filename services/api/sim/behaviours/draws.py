"""Keyed, stateless uniform draws for the group behaviours.

A draw is SHA-256 of a compact encoding of `(seed, "behaviour", group_id, member_id, tick,
purpose)`, scaled by 2**-53 (exact), the same pattern as the assist's `keyed_uniform`. It needs no
random stream in `sim/rng.py`, so adding behaviours cannot shift any other subsystem's numbers,
and the value for a member and tick does not depend on which other draws were taken or in what
order. Hash draws are the cost of the noise and link models, so `Draws` counts them for the
performance test.
"""

import hashlib
import json

_TWO53 = 9007199254740992.0  # 2**53, written out so no float power is ever taken


def uniform(seed: int, group_id: str, member_id: str, tick: int, purpose: str) -> float:
    """A double in [0, 1) from the first 53 bits of the keyed SHA-256."""
    payload = json.dumps(
        [seed, "behaviour", group_id, member_id, tick, purpose],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("ascii")).digest()
    return float(int.from_bytes(digest[:8], "big") >> 11) / _TWO53


def signed(seed: int, group_id: str, member_id: str, tick: int, purpose: str) -> float:
    """A double in [-1, 1) from the same keyed draw."""
    return 2.0 * uniform(seed, group_id, member_id, tick, purpose) - 1.0


class Draws:
    """The draws of one group: a seed and group ID, and a count of the hash draws taken."""

    def __init__(self, seed: int, group_id: str) -> None:
        self.seed = seed
        self.group_id = group_id
        self.count = 0

    def uniform(self, member_id: str, tick: int, purpose: str) -> float:
        self.count += 1
        return uniform(self.seed, self.group_id, member_id, tick, purpose)

    def signed(self, member_id: str, tick: int, purpose: str) -> float:
        return 2.0 * self.uniform(member_id, tick, purpose) - 1.0
