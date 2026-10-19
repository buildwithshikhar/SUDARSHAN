"""Threat catalogue: the drone and clutter classes a scenario may fly (docs/THREAT_CATALOGUE.md).

The classes are `threat-class.v1` packs in `packs/threats/`. This module loads them, answers the
questions the rest of the sim asks about a class (what is it scored as, how may it move), checks a
scenario against the catalogue, and checks that every sensor profile covers every class, so a
class cannot be added without the sensors learning about it (Q-21).

`python -m sim.catalogue` prints the markdown tables that docs/THREAT_CATALOGUE.md embeds.
"""

import math
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import ValidationError

from app.contracts.loader import PackError, load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import KinematicLimits, ScenarioSpec
from app.contracts.threat_class import ENVELOPE_UNITS, SIGNATURE_UNITS, ThreatClass

from .sensors import MODELS, ProfileError, SensorParams

#: Confusion tables whose labels are not class names (radar micro-Doppler signatures).
_SIGNATURE_TABLES = frozenset({"micro_doppler"})
#: Signature parameters each modality reads per class. `eo` contrast is derived (see below).
PROFILE_PARAMS: dict[str, tuple[str, ...]] = {
    "radar": ("rcs", "aspect_swing"),
    "eo": ("size", "contrast"),
    "ir": ("size", "contrast"),
    "rf": ("emits", "emitter_power", "band", "hop_rate"),
    "acoustic": ("source_level", "blades", "rpm", "harmonics"),
}
#: Profile values may differ from the catalogue by this much (EO contrast is a rounded product).
TOLERANCE = 1e-9


class CatalogueError(ValueError):
    """The threat packs are missing, malformed or inconsistent with each other."""


class Catalogue:
    """The loaded classes, in class-ID order."""

    def __init__(self, classes: Iterable[ThreatClass]) -> None:
        self._classes = {c.id: c for c in sorted(classes, key=lambda c: c.id)}

    def __iter__(self) -> Iterator[ThreatClass]:
        return iter(self._classes.values())

    def __len__(self) -> int:
        return len(self._classes)

    def __contains__(self, class_id: object) -> bool:
        return class_id in self._classes

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._classes)

    def get(self, class_id: str) -> ThreatClass:
        """The class with this ID; `KeyError` when the catalogue has none."""
        try:
            return self._classes[class_id]
        except KeyError:
            raise KeyError(f"threat catalogue has no class {class_id!r}") from None

    def recognition_class(self, class_id: str) -> str:
        """The operator-vocabulary class the truth class is scored as; `KeyError` if unknown."""
        return self.get(class_id).recognition_class

    @property
    def recognition_set(self) -> frozenset[str]:
        return frozenset(c.recognition_class for c in self)

    def limits_for(self, class_id: str) -> KinematicLimits:
        """The widest kinematic limits a threat of the class may carry."""
        return self.get(class_id).envelope.to_limits()

    def check_scenario(self, spec: ScenarioSpec) -> list[str]:
        """Problems with a scenario's threats: unknown class, limits wider than the class allows,
        a disposition the class category cannot have. Empty when the scenario is consistent."""
        problems: list[str] = []
        for threat in spec.threats:
            if threat.class_id not in self:
                problems.append(
                    f"threat {threat.id}: class {threat.class_id!r} is not in the catalogue"
                )
                continue
            cls = self.get(threat.class_id)
            allowed, used = cls.envelope.to_limits(), threat.limits
            for field in (
                "max_speed_mps",
                "max_accel_mps2",
                "max_climb_mps",
                "max_descent_mps",
                "max_turn_rate_dps",
            ):
                if getattr(used, field) > getattr(allowed, field):
                    problems.append(
                        f"threat {threat.id}: {field} {getattr(used, field):g} is above the "
                        f"{cls.id} envelope ({getattr(allowed, field):g})"
                    )
            if used.min_altitude_m < allowed.min_altitude_m:
                problems.append(
                    f"threat {threat.id}: min_altitude_m {used.min_altitude_m:g} is below the "
                    f"{cls.id} envelope ({allowed.min_altitude_m:g})"
                )
            if used.max_altitude_m > allowed.max_altitude_m:
                problems.append(
                    f"threat {threat.id}: max_altitude_m {used.max_altitude_m:g} is above the "
                    f"{cls.id} envelope ({allowed.max_altitude_m:g})"
                )
            if (cls.category == "clutter") != (threat.disposition == "clutter"):
                problems.append(
                    f"threat {threat.id}: disposition {threat.disposition!r} does not fit a "
                    f"{cls.category} class"
                )
        return problems


def load_catalogue(directory: Path | None = None) -> Catalogue:
    """Read every `<id>.v1.yaml` under `packs/threats/` (or `directory`) and cross-check them."""
    root = packs_root() / "threats" if directory is None else directory
    paths = sorted(root.glob("*.v1.yaml")) if root.is_dir() else []
    if not paths:
        raise CatalogueError(f"no threat class packs in {root}")
    classes: list[ThreatClass] = []
    for path in paths:
        try:
            pack = load_pack(path)
        except (PackError, ValidationError) as error:
            raise CatalogueError(f"{path.name}: {error}") from error
        if not isinstance(pack, ThreatClass):
            raise CatalogueError(f"{path.name}: not a threat class")
        if path.name != f"{pack.id}.v1.yaml":
            raise CatalogueError(f"{path.name}: the file must be named {pack.id}.v1.yaml")
        classes.append(pack)
    catalogue = Catalogue(classes)
    for cls in catalogue:
        target = catalogue._classes.get(cls.recognition_class)  # noqa: SLF001 - same module
        if target is None or target.recognition_class != target.id:
            raise CatalogueError(
                f"{cls.id}: recognition_class {cls.recognition_class!r} is not a class that "
                "is recognised as itself"
            )
    return catalogue


# ---------------------------------------------------------------------------- profile coverage


def _expected(params: SensorParams, cls: ThreatClass, prefix: str) -> float:
    """The value the profile must give the class for `prefix`.

    Visible-band cameras (`eo`) scale their own `contrast_default` by the class's `contrast_eo`;
    everything else is the catalogue value.
    """
    if params.modality == "eo" and prefix == "contrast":
        return params.value("contrast_default", "ratio") * cls.signature["contrast_eo"].value
    return cls.signature[prefix].value


def profile_problems(catalogue: Catalogue, profiles: Iterable[SensorParams]) -> list[str]:
    """Where a sensor profile disagrees with the catalogue or does not cover a class.

    Per-class parameters must resolve (through `<prefix>_default` when not listed) to the
    catalogue's signature value; a parameter the profile lists for the class must also carry the
    catalogue's unit, register ID and verified flag; every confusion table the model samples must
    have a row for the class that sums to 1, and must be able to say `unknown` and the class's
    recognition label (RF labels only what a class emits).
    """
    problems: list[str] = []
    for params in profiles:
        keys = MODELS[params.modality].confusion_keys
        for cls in catalogue:
            for prefix in PROFILE_PARAMS[params.modality]:
                name = f"{prefix}_{cls.id.replace('-', '_')}"
                unit = SIGNATURE_UNITS[prefix]
                try:
                    actual = params.for_class(prefix, cls.id, unit)
                except ProfileError as error:
                    problems.append(str(error))
                    continue
                want = _expected(params, cls, prefix)
                if not math.isclose(actual, want, rel_tol=TOLERANCE, abs_tol=TOLERANCE):
                    problems.append(
                        f"{params.id}: {name} is {actual:g}, the catalogue says {want:g}"
                    )
                derived = params.modality == "eo" and prefix == "contrast"
                if name in params and not derived:
                    listed, source = params.quantity(name), cls.signature[prefix]
                    if (listed.source_id, listed.verified) != (source.source_id, source.verified):
                        problems.append(
                            f"{params.id}: {name} cites {listed.source_id} "
                            f"(verified {listed.verified}), the catalogue cites "
                            f"{source.source_id} (verified {source.verified})"
                        )
            for key in keys:
                table = params.profile.confusion[key]
                if cls.id not in table.rows:
                    problems.append(f"{params.id}: confusion table {key!r} has no row for {cls.id}")
                    continue
                if key in _SIGNATURE_TABLES:
                    continue
                needed = ["unknown"]
                if params.modality != "rf" or cls.signature["emits"].value >= 0.5:
                    needed.append(cls.recognition_class)
                missing = [label for label in needed if label not in table.labels]
                if missing:
                    problems.append(
                        f"{params.id}: confusion table {key!r} cannot report {', '.join(missing)}"
                        f" for {cls.id}"
                    )
    return problems


# ---------------------------------------------------------------------------- markdown


def _cell(q_value: float, source_id: str) -> str:
    text = f"{q_value:g}"
    return text if source_id == "F01" else f"{text} [{source_id}]"


def _table(
    catalogue: Catalogue, group: str, names: tuple[str, ...], units: dict[str, str]
) -> list[str]:
    head = ["Class", *(f"`{n}` ({units[n]})" for n in names), "Register", "Verified"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for cls in catalogue:
        quantities = (
            [getattr(cls.envelope, n) for n in names]
            if group == "envelope"
            else [cls.signature[n] for n in names]
        )
        register = sorted({q.source_id for q in quantities})
        verified = [n for n, q in zip(names, quantities, strict=True) if q.verified]
        cells = [_cell(q.value, q.source_id) for q in quantities]
        row = [f"`{cls.id}`", *cells, ", ".join(register), ", ".join(verified) or "none"]
        lines.append("| " + " | ".join(row) + " |")
    return lines


def markdown(catalogue: Catalogue) -> str:
    """The generated tables of docs/THREAT_CATALOGUE.md. A value that cites a register ID other
    than F01 shows it in brackets; the Verified column lists the verified parameters."""
    lines = [
        "#### Classes",
        "",
        "| Class | Category | Scored as | UAS group | Default disposition | Summary |",
        "|---|---|---|---|---|---|",
    ]
    for cls in catalogue:
        group = cls.uas_group or "none"
        lines.append(
            f"| `{cls.id}` | {cls.category} | `{cls.recognition_class}` | {group} | "
            f"{cls.default_disposition} | {cls.summary.en} |"
        )
    envelope_names = tuple(ENVELOPE_UNITS)
    lines += ["", "#### Envelope", ""]
    lines += _table(catalogue, "envelope", envelope_names, ENVELOPE_UNITS)
    optical = ("rcs", "aspect_swing", "size", "contrast", "contrast_eo")
    link = tuple(n for n in SIGNATURE_UNITS if n not in optical)
    lines += ["", "#### Signature: radar, camera and thermal parameters", ""]
    lines += _table(catalogue, "signature", optical, SIGNATURE_UNITS)
    lines += ["", "#### Signature: RF and acoustic parameters", ""]
    lines += _table(catalogue, "signature", link, SIGNATURE_UNITS)
    return "\n".join(lines) + "\n"


def main() -> int:
    print(markdown(load_catalogue()), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
