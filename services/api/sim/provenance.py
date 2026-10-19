"""Which pack versions a session used, and the lock that stops a pack changing under its version.

A sensor profile, a threat class or a rule pack carries numbers a score depends on. Two things keep
a stored score honest about them:

- A stored session and its score record the profile and threat-class versions they used
  (`used_versions`), and a replay refuses a record whose versions are not the ones loaded now
  (`check_recorded`) instead of replaying it with other numbers.
- `packs/versions.lock.json` holds a hash of the content of every such pack beside its version
  (`lock_problems`). A pack whose content changed without a version bump fails a test, and the
  refresh command (`python -m app.cli pack-lock`) refuses to record new content under an old
  version.

The hash covers the validated content without the `version` field, so comments and formatting in
the YAML do not matter and a version bump alone does not change it.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.contracts.common import PackRef
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.rulepack import RulePack
from app.contracts.scenario import ScenarioSpec
from app.contracts.sensor_profile import SensorProfile
from app.contracts.threat_class import ThreatClass

from .canonical import sha256_hex

LOCK_NAME = "versions.lock.json"
#: Lock keys are `<kind>/<id>`; the kinds, the directory holding each and the file pattern.
KINDS: dict[str, tuple[str, str]] = {
    "sensor-profile": ("sensor-profiles", "*.yaml"),
    "threat-class": ("threats", "*.v1.yaml"),
    "rule-pack": ("rule-packs", "*.v1.yaml"),
}
_NOTE = (
    "Content hash of every sensor profile, threat class and rule pack, beside its version. A pack "
    "whose content changes needs a higher version; refresh with `python -m app.cli pack-lock`, "
    "which refuses new content under an old version."
)


class VersionMismatch(ValueError):
    """A stored record was made with other pack versions than the ones loaded now."""


@dataclass(frozen=True, slots=True)
class UsedVersions:
    """The sensor profiles and threat classes a scenario's session uses, by exact version."""

    profiles: tuple[PackRef, ...]
    threat_classes: tuple[PackRef, ...]


def _ref(id_: str, version: str) -> PackRef:
    return PackRef(id=id_, version=version)


def used_versions(spec: ScenarioSpec, root: Path | None = None) -> UsedVersions:
    """The versions in force for `spec`: its pinned sensor profiles, and the catalogue version of
    every threat class it flies. Sorted by ID, one entry each."""
    from .catalogue import load_catalogue

    directory = None if root is None else root / "threats"
    catalogue = load_catalogue(directory)
    profiles = {(s.profile.id, s.profile.version) for s in spec.sensors}
    classes = {(c, catalogue.get(c).version) for c in {t.class_id for t in spec.threats}}
    return UsedVersions(
        profiles=tuple(_ref(i, v) for i, v in sorted(profiles)),
        threat_classes=tuple(_ref(i, v) for i, v in sorted(classes)),
    )


def check_recorded(
    spec: ScenarioSpec,
    profiles: Iterable[PackRef],
    threat_classes: Iterable[PackRef],
    root: Path | None = None,
) -> None:
    """Refuse a record made with other versions. A record made before versions were recorded has
    none, and is not checked."""
    recorded = (tuple(profiles), tuple(threat_classes))
    if not any(recorded):
        return
    now = used_versions(spec, root)
    for what, was, is_ in (
        ("sensor profile", recorded[0], now.profiles),
        ("threat class", recorded[1], now.threat_classes),
    ):
        if was != is_:
            wrote = ", ".join(f"{r.id} {r.version}" for r in was) or "none"
            have = ", ".join(f"{r.id} {r.version}" for r in is_) or "none"
            raise VersionMismatch(
                f"the session was recorded with {what} versions [{wrote}], "
                f"the packs now loaded are [{have}]"
            )


# ---------------------------------------------------------------------------- the lock

Pack = SensorProfile | ThreatClass | RulePack


def content_hash(pack: Pack) -> str:
    """SHA-256 of the pack's validated content, leaving out its `version`."""
    return sha256_hex(pack.model_dump(mode="json", exclude={"version"}))


def _semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def current_entries(root: Path | None = None) -> dict[str, dict[str, str]]:
    """The lock entries the pack files give now, keyed `<kind>/<id>`."""
    base = packs_root() if root is None else root
    out: dict[str, dict[str, str]] = {}
    for kind, (directory, pattern) in KINDS.items():
        for path in sorted((base / directory).glob(pattern)):
            pack = load_pack(path)
            if not isinstance(pack, SensorProfile | ThreatClass | RulePack):
                raise ValueError(f"{path.name}: not a {kind}")
            out[f"{kind}/{pack.id}"] = {
                "version": pack.version,
                "content_sha256": content_hash(pack),
            }
    return out


def read_lock(root: Path | None = None) -> dict[str, dict[str, str]]:
    path = (packs_root() if root is None else root) / LOCK_NAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, str]] = data["entries"]
    return entries


def lock_problems(root: Path | None = None) -> list[str]:
    """Where the packs and the lock disagree. Empty when every pack is locked at its version and
    content."""
    now, locked = current_entries(root), read_lock(root)
    problems: list[str] = []
    for key, entry in now.items():
        was = locked.get(key)
        if was is None:
            problems.append(f"{key}: not in {LOCK_NAME}; run `python -m app.cli pack-lock`")
        elif (
            was["version"] == entry["version"] and was["content_sha256"] != entry["content_sha256"]
        ):
            problems.append(
                f"{key}: content changed but the version is still {entry['version']}; "
                "bump the version, then run `python -m app.cli pack-lock`"
            )
        elif was != entry:
            problems.append(
                f"{key}: version is {entry['version']} but {LOCK_NAME} has {was['version']}; "
                "run `python -m app.cli pack-lock`"
            )
    problems += [f"{key}: in {LOCK_NAME} but the pack is gone" for key in locked if key not in now]
    return problems


def refresh_lock(root: Path | None = None) -> list[str]:
    """Write the lock from the packs and return a line per entry that changed.

    Refuses (`ValueError`) to record new content under the version already locked, or a version
    lower than the locked one, so the lock cannot be refreshed past a missing bump.
    """
    now, locked = current_entries(root), read_lock(root)
    refused: list[str] = []
    changes: list[str] = []
    for key, entry in now.items():
        was = locked.get(key)
        if was is None:
            changes.append(f"{key}: added at {entry['version']}")
        elif was == entry:
            continue
        elif _semver(entry["version"]) < _semver(was["version"]):
            refused.append(f"{key}: version went down, {was['version']} to {entry['version']}")
        elif (
            was["content_sha256"] != entry["content_sha256"] and was["version"] == entry["version"]
        ):
            refused.append(f"{key}: content changed under version {entry['version']}; bump it")
        else:
            changes.append(f"{key}: {was['version']} to {entry['version']}")
    if refused:
        raise ValueError("; ".join(refused))
    changes += [f"{key}: removed" for key in locked if key not in now]
    path = (packs_root() if root is None else root) / LOCK_NAME
    body = {"note": _NOTE, "entries": dict(sorted(now.items()))}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changes
