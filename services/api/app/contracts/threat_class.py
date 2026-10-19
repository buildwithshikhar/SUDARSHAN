"""Threat class, contract `threat-class.v1` (authored as YAML in `packs/threats/`).

One file per class of contact: how it may move (a kinematic envelope) and what it looks, sounds
and transmits like (a signature, in the parameter names the sensor profiles use). Kinematics and
signatures only: the contract has no field for guidance, payload, targeting or any way to build or
operate a vehicle. Every value carries its unit, data-register ID and `verified` flag.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import Contract, ParamName, Quantity, SemVer, Slug, Text
from .scenario import Disposition, KinematicLimits

#: Unit each envelope quantity is written in (the units of `scenario.KinematicLimits`).
ENVELOPE_UNITS: dict[str, str] = {
    "max_speed": "m/s",
    "cruise_speed": "m/s",
    "max_accel": "m/s2",
    "max_climb": "m/s",
    "max_descent": "m/s",
    "max_turn_rate": "deg/s",
    "min_altitude": "m",
    "max_altitude": "m",
}

#: Signature parameters and their units: the sensor-profile names without the `_<class>` suffix.
#: `contrast` is the thermal contrast (1.0 is the multirotor reference); `contrast_eo` is the
#: visible-band contrast as a factor of the EO camera's `contrast_default`.
SIGNATURE_UNITS: dict[str, str] = {
    "rcs": "dBsm",
    "aspect_swing": "dB",
    "size": "m",
    "contrast": "ratio",
    "contrast_eo": "ratio",
    "emits": "flag",
    "emitter_power": "dBm",
    "band": "index",
    "hop_rate": "Hz",
    "source_level": "dB",
    "blades": "count",
    "rpm": "rpm",
    "harmonics": "count",
}

#: Band indices of the RF model's band plan (`sim.sensors.rf.BANDS`).
BAND_COUNT = 5


class Envelope(Contract):
    """How the class may move: the limits a scenario threat stays inside, plus a cruise speed."""

    max_speed: Quantity
    cruise_speed: Quantity
    max_accel: Quantity
    max_climb: Quantity
    max_descent: Quantity
    max_turn_rate: Quantity
    min_altitude: Quantity
    max_altitude: Quantity

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name, unit in ENVELOPE_UNITS.items():
            quantity: Quantity = getattr(self, name)
            if quantity.unit != unit:
                raise ValueError(f"envelope {name} is in {quantity.unit!r}, expected {unit!r}")
            if quantity.value < 0 or (quantity.value == 0 and name != "min_altitude"):
                raise ValueError(f"envelope {name} must be positive")
        if self.cruise_speed.value > self.max_speed.value:
            raise ValueError("envelope cruise_speed is above max_speed")
        if self.min_altitude.value >= self.max_altitude.value:
            raise ValueError("envelope min_altitude must be below max_altitude")
        self.to_limits()  # also refuses a value outside what a scenario threat may carry
        return self

    def to_limits(self) -> KinematicLimits:
        """The scenario form of this envelope (the widest limits a threat of the class may use)."""
        return KinematicLimits(
            max_speed_mps=self.max_speed.value,
            max_accel_mps2=self.max_accel.value,
            max_climb_mps=self.max_climb.value,
            max_descent_mps=self.max_descent.value,
            max_turn_rate_dps=self.max_turn_rate.value,
            min_altitude_m=self.min_altitude.value,
            max_altitude_m=self.max_altitude.value,
        )


class ThreatClass(Contract):
    contract: Literal["threat-class.v1"]
    #: The class ID used as a truth class in scenarios and in sensor tables.
    id: Slug
    version: SemVer
    title: Text
    summary: Text
    fictional: Literal[True]
    category: Literal["drone", "clutter"]
    #: The operator-vocabulary class this class is scored as (itself, or its look-alike family).
    recognition_class: Slug
    default_disposition: Disposition
    #: US DoD UAS group as a neutral public reference (docs/02-research.md section 2); `None` for
    #: clutter. A label, not a bound: the group figures are not checked against the envelope.
    uas_group: Literal["1", "2", "3"] | None
    envelope: Envelope
    signature: Annotated[
        dict[ParamName, Quantity],
        Field(min_length=1, max_length=32, json_schema_extra={"additionalProperties": False}),
    ]
    notes: Text | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.category == "clutter":
            if self.default_disposition != "clutter":
                raise ValueError("a clutter class must have the clutter disposition")
            if self.uas_group is not None:
                raise ValueError("a clutter class has no UAS group")
        else:
            if self.default_disposition == "clutter":
                raise ValueError("a drone class cannot have the clutter disposition")
            if self.uas_group is None:
                raise ValueError("a drone class needs a UAS group")
        missing = sorted(set(SIGNATURE_UNITS) - set(self.signature))
        extra = sorted(set(self.signature) - set(SIGNATURE_UNITS))
        if missing or extra:
            raise ValueError(f"signature: missing {missing}, unknown {extra}")
        for name, unit in SIGNATURE_UNITS.items():
            if self.signature[name].unit != unit:
                raise ValueError(
                    f"signature {name} is in {self.signature[name].unit!r}, expected {unit!r}"
                )
        sig = {name: q.value for name, q in self.signature.items()}
        for name in ("size", "contrast", "contrast_eo"):
            if sig[name] <= 0:
                raise ValueError(f"signature {name} must be positive")
        for name in ("aspect_swing", "hop_rate", "blades", "rpm"):
            if sig[name] < 0:
                raise ValueError(f"signature {name} cannot be negative")
        if sig["emits"] not in (0.0, 1.0):
            raise ValueError("signature emits must be 0 or 1")
        if sig["band"] not in {float(i) for i in range(1, BAND_COUNT + 1)}:
            raise ValueError(f"signature band must be an index from 1 to {BAND_COUNT}")
        if sig["harmonics"] < 1 or sig["harmonics"] != int(sig["harmonics"]):
            raise ValueError("signature harmonics must be a whole number of at least 1")
        return self
