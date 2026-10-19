"""The generator's request: what an instructor, the curriculum or (wave 11a) the learner model asks
for. Plain data, so it round-trips through a seed-share code byte for byte."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.contracts.common import Contract, Seed

#: The version of the generator's sampler and constraints. Same seed and version, same spec.
GENERATOR_VERSION = "1.0.0"

Terrain = Literal["flat", "heron-ridge", "osprey-town"]
TimeOfDay = Literal["dawn", "day", "dusk", "night"]
Weather = Literal["clear", "haze", "rain", "fog", "dust"]
Archetype = Literal["single", "swarm", "fast-mover", "fixed-wing", "decoy-mix", "silent-raid"]

TERRAINS: tuple[str, ...] = ("flat", "heron-ridge", "osprey-town")
TIMES_OF_DAY: tuple[str, ...] = ("dawn", "day", "dusk", "night")
WEATHERS: tuple[str, ...] = ("clear", "haze", "rain", "fog", "dust")
ARCHETYPES: tuple[str, ...] = (
    "single",
    "swarm",
    "fast-mover",
    "fixed-wing",
    "decoy-mix",
    "silent-raid",
)

Percent = Annotated[int, Field(ge=0, le=100)]


class DifficultyVector(Contract):
    """Five independent difficulty axes, each 0 to 100 (whole numbers, so a request is exact)."""

    #: How much arrives and how much of it is hostile (one drone up to a large formation).
    threat_load: Percent = 40
    #: How many look-alikes surround the hostile contacts (birds, kites, civil flights, decoys).
    ambiguity: Percent = 40
    #: How fast the hostile contacts close in, which sets the time to answer.
    speed: Percent = 40
    #: How hard they are to sense: low radar return, no radio, low flying, little thermal contrast.
    stealth: Percent = 40
    #: How badly the sensors are degraded (outages, haze, interference) and for how long.
    degradation: Percent = 0


class GeneratorRequest(Contract):
    seed: Seed
    terrain: Terrain = "flat"
    time_of_day: TimeOfDay = "day"
    weather: Weather = "clear"
    difficulty: DifficultyVector = DifficultyVector()
    #: Which kinds of threat may be drawn; kept in the order of `ARCHETYPES`.
    threat_mix: Annotated[list[Archetype], Field(min_length=1, max_length=6)] = [
        "single",
        "swarm",
        "fast-mover",
        "fixed-wing",
        "decoy-mix",
        "silent-raid",
    ]
    #: The lowest contact score (percent) the oracle defender may reach on a hostile contact for
    #: the scenario to count as solved. 100 asks for the scoring's maximum.
    oracle_min_score: Annotated[int, Field(ge=50, le=100)] = 80
    #: Candidates tried before the softest constraint is relaxed (and again after each relaxation).
    max_attempts: Annotated[int, Field(ge=1, le=64)] = 12

    @field_validator("threat_mix")
    @classmethod
    def _canonical(cls, mix: list[str]) -> list[str]:
        if len(set(mix)) != len(mix):
            raise ValueError("threat_mix lists an archetype twice")
        return [a for a in ARCHETYPES if a in mix]


__all__ = [
    "ARCHETYPES",
    "GENERATOR_VERSION",
    "TERRAINS",
    "TIMES_OF_DAY",
    "WEATHERS",
    "DifficultyVector",
    "GeneratorRequest",
    "Seed",
]
