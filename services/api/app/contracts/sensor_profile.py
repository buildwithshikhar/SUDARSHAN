"""Sensor profile, contract `sensor-profile.v1` (authored as YAML).

Only the parameter container is fixed here; the sensor models that read it arrive in wave 4a.
Every numeric parameter carries its unit, data-register source and verification flag.
"""

from typing import Annotated, Literal

from pydantic import Field

from .common import Contract, ParamName, Quantity, SemVer, Slug, Text


class SensorProfile(Contract):
    contract: Literal["sensor-profile.v1"]
    id: Slug
    version: SemVer
    title: Text
    modality: Literal["radar", "eo", "ir", "rf", "acoustic"]
    fictional: Literal[True]
    parameters: Annotated[
        dict[ParamName, Quantity],
        # patternProperties alone lets other names through, so close the object in the schema too
        Field(min_length=1, max_length=64, json_schema_extra={"additionalProperties": False}),
    ]
    notes: Text | None = None
