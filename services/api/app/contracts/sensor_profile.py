"""Sensor profile, contract `sensor-profile.v1` (authored as YAML).

The container is fixed in wave 3; the sensor models that read it live in `sim/sensors/`.
Every numeric parameter carries its unit, data-register source and verification flag. A class
confusion table is one provenance-carrying object, so its source applies to the whole matrix.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import Contract, ParamName, Quantity, SemVer, Slug, SourceId, Text

#: Largest allowed deviation of a confusion row's sum from 1.
ROW_SUM_TOLERANCE = 1e-9


class ConfusionTable(Contract):
    """How a sensor labels each true class: one row per true class, one column per label.

    Rows are probabilities and sum to 1 (row-normalised). The columns are the labels the sensor
    can report, `unknown` included; the true classes need not be a subset of them.
    """

    labels: Annotated[list[Slug], Field(min_length=2, max_length=32)]
    rows: Annotated[
        dict[Slug, list[Annotated[float, Field(ge=0, le=1)]]],
        Field(min_length=1, max_length=64),
    ]
    source_id: SourceId
    verified: bool = Field(description="True only when the matrix was checked against the source.")

    @model_validator(mode="after")
    def _row_normalised(self) -> Self:
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("confusion labels must be unique")
        for true_class, row in self.rows.items():
            if len(row) != len(self.labels):
                raise ValueError(f"confusion row {true_class!r} needs {len(self.labels)} entries")
            if abs(sum(row) - 1.0) > ROW_SUM_TOLERANCE:
                raise ValueError(f"confusion row {true_class!r} must sum to 1, not {sum(row)}")
        return self


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
    #: Class confusion tables by context (for example `default`, `thermal`).
    confusion: Annotated[dict[ParamName, ConfusionTable], Field(max_length=8)] = {}
    notes: Text | None = None
