"""Seeded random streams, one per subsystem.

Each stream is a numpy PCG64 generator seeded from `SeedSequence(seed, spawn_key=(key(name),))`,
where the key is the first 8 bytes of SHA-256 of the stream name. A stream therefore depends only
on the scenario seed and its own name: adding a stream, or drawing more numbers from one, never
shifts any other. Python's `hash()` is never used because it is salted per process.
"""

import hashlib
from typing import Any

import numpy as np

#: Every stream the core may draw from. New subsystems add a name here; existing ones never move.
STREAMS: tuple[str, ...] = ("weather", "kinematics", "spawn", "sensors", "tracking", "adversary")


def stream_key(name: str) -> int:
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "big")


class RngStreams:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._streams = {
            name: np.random.Generator(
                np.random.PCG64(np.random.SeedSequence(seed, spawn_key=(stream_key(name),)))
            )
            for name in STREAMS
        }

    def __getitem__(self, name: str) -> np.random.Generator:
        return self._streams[name]

    def uniform(self, name: str) -> float:
        """One double in [0, 1): 53 random bits times 2**-53, exact on every platform."""
        return float(self._streams[name].random())

    def normalish(self, name: str) -> float:
        """Zero-mean, unit-variance, bounded (|x| <= 2 * sqrt(3)) draw from four uniforms.

        numpy's normal sampler can call the platform `log` in its tail; a sum of uniforms uses only
        exact arithmetic, and its bounded tails keep gusts physically plausible.
        """
        total = 0.0
        for _ in range(4):
            total += self.uniform(name)
        return (total - 2.0) * 1.7320508075688772

    def state(self) -> dict[str, Any]:
        return {name: self._streams[name].bit_generator.state for name in STREAMS}

    def restore(self, state: dict[str, Any]) -> None:
        if sorted(state) != sorted(STREAMS):
            raise ValueError("snapshot RNG streams do not match this sim core")
        for name in STREAMS:
            self._streams[name].bit_generator.state = state[name]
