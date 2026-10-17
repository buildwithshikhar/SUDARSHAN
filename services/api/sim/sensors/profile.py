"""Sensor profiles as the sensor models read them.

A profile is a `sensor-profile.v1` pack (see `app.contracts.sensor_profile`). The contract already
refuses a parameter without a unit, a data-register ID and a `verified` flag. This module adds the
checks a model needs: that the ID is a row in the register, that the unit is the one the model
expects, that every required parameter is present, and a list of the values still marked
`verified: false` so documents and the UI can show the uncertainty.
"""

import re
from collections.abc import Collection
from pathlib import Path

from app.contracts.common import PackRef, Quantity
from app.contracts.loader import PackError, load_pack
from app.contracts.sensor_profile import SensorProfile

from .confusion import ConfusionMatrix

DEFAULT_CLASS = "default"
_REGISTER_ROW = re.compile(r"^\| ([DGWXF][0-9]{2}) \|", re.MULTILINE)


class ProfileError(ValueError):
    """A sensor profile cannot drive the model that was asked to use it."""


def register_ids(register_md: Path) -> frozenset[str]:
    """Source IDs that have a row in docs/DATA_REGISTER.md."""
    return frozenset(_REGISTER_ROW.findall(register_md.read_text(encoding="utf-8")))


class SensorParams:
    """Read access to one validated profile; every lookup names the profile when it fails."""

    def __init__(self, profile: SensorProfile) -> None:
        self.profile = profile
        self._confusion = {key: ConfusionMatrix(t) for key, t in profile.confusion.items()}

    @property
    def id(self) -> str:
        return self.profile.id

    @property
    def version(self) -> str:
        return self.profile.version

    @property
    def modality(self) -> str:
        return self.profile.modality

    def __contains__(self, name: str) -> bool:
        return name in self.profile.parameters

    def quantity(self, name: str) -> Quantity:
        try:
            return self.profile.parameters[name]
        except KeyError:
            raise ProfileError(f"profile {self.id}: parameter {name!r} is missing") from None

    def value(self, name: str, unit: str | None = None) -> float:
        """The parameter's value; with `unit`, refuses a profile written in another unit."""
        q = self.quantity(name)
        if unit is not None and q.unit != unit:
            raise ProfileError(f"profile {self.id}: {name!r} is in {q.unit!r}, expected {unit!r}")
        return q.value

    def optional(self, name: str, unit: str | None = None) -> float | None:
        return self.value(name, unit) if name in self else None

    def require(self, *names: str) -> None:
        missing = [n for n in names if n not in self]
        if missing:
            raise ProfileError(f"profile {self.id}: missing parameters {', '.join(missing)}")

    def for_class(self, prefix: str, class_id: str, unit: str | None = None) -> float:
        """Per-class parameter `<prefix>_<class_id>` (hyphens become underscores).

        Falls back to `<prefix>_default`, so a profile can give one figure for every class it does
        not list; with neither present the profile is refused.
        """
        name = f"{prefix}_{class_id.replace('-', '_')}"
        return self.value(name if name in self else f"{prefix}_{DEFAULT_CLASS}", unit)

    def confusion(self, key: str = DEFAULT_CLASS) -> ConfusionMatrix:
        try:
            return self._confusion[key]
        except KeyError:
            raise ProfileError(f"profile {self.id}: confusion table {key!r} is missing") from None

    @property
    def unverified(self) -> tuple[str, ...]:
        """Names of parameters and confusion tables still marked `verified: false`, sorted."""
        names = [n for n, q in self.profile.parameters.items() if not q.verified]
        names += [f"confusion:{k}" for k, t in self.profile.confusion.items() if not t.verified]
        return tuple(sorted(names))

    def check_sources(self, register: Collection[str]) -> None:
        """Refuse any parameter or table whose `source_id` is not a row in the data register."""
        bad = [n for n, q in self.profile.parameters.items() if q.source_id not in register]
        bad += [
            f"confusion:{k}"
            for k, t in self.profile.confusion.items()
            if t.source_id not in register
        ]
        if bad:
            names = ", ".join(sorted(bad))
            raise ProfileError(
                f"profile {self.id}: source IDs not in the data register for {names}"
            )


def load_sensor_profile(path: Path, *, register: Collection[str] | None = None) -> SensorParams:
    """Read and validate one profile file; with `register`, also check every source ID."""
    try:
        pack = load_pack(path)
    except (PackError, ValueError) as error:
        raise ProfileError(f"{path.name}: {error}") from error
    if not isinstance(pack, SensorProfile):
        raise ProfileError(f"{path.name}: not a sensor profile")
    params = SensorParams(pack)
    if register is not None:
        params.check_sources(register)
    return params


def resolve_profile(
    ref: PackRef, directory: Path, *, register: Collection[str] | None = None
) -> SensorParams:
    """Find the profile with exactly this ID and version in a pack directory."""
    for path in sorted(directory.glob("*.yaml")):
        params = load_sensor_profile(path, register=register)
        if (params.id, params.version) == (ref.id, ref.version):
            return params
    raise ProfileError(f"no sensor profile {ref.id} {ref.version} in {directory}")
