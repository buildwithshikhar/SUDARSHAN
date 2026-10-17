"""Shared building blocks for the versioned contracts.

Every contract model forbids unknown fields and is immutable once validated, so a pack that
loads is exactly the pack that was written.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints

#: Data-register ID (docs/DATA_REGISTER.md): D datasets, G geodata, W weather, X specifications,
#: F project-authored fictional values.
SourceId = Annotated[str, StringConstraints(pattern=r"^[DGWXF][0-9]{2}$")]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]
SemVer = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}$")]
ParamName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
Unit = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z%°µ][A-Za-z0-9%°µ/^.\-]*$", max_length=24)
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Seed = Annotated[int, Field(ge=0, le=2**63 - 1)]
Heading = Annotated[float, Field(ge=0, lt=360)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Text(Contract):
    """User-facing text in both interface languages."""

    en: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    hi: Annotated[str, StringConstraints(min_length=1, max_length=400)]


class Quantity(Contract):
    """A numeric parameter with its unit and provenance."""

    value: FiniteFloat
    unit: Unit
    source_id: SourceId
    verified: bool = Field(description="True only when the value was checked against the source.")


class Vec3(Contract):
    """Local east-north-up position in metres; z is height above the flat ground plane."""

    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat


class PackRef(Contract):
    """Reference to another versioned pack by ID and exact version."""

    id: Slug
    version: SemVer


def unique(ids: list[str], what: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            raise ValueError(f"duplicate {what} id {item!r}")
        seen.add(item)
