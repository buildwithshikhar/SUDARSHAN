"""The scenarios a trainee can play: those whose sensors and rules load."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import ScenarioSpec
from sim.roe import RuleEngine, load_rule_engine
from sim.tracking.picture import Picture

log = logging.getLogger("app.live")


@dataclass(frozen=True)
class CatalogEntry:
    spec: ScenarioSpec
    #: The rule engine is a pure function of the pack, so sessions share it.
    engine: RuleEngine
    #: Sensor modality by sensor ID, for the briefing.
    modalities: dict[str, str]


class SavedScenarios(Protocol):
    """Where scenarios kept beyond the packs are looked up (`app.scenarios.store.ScenarioStore`)."""

    def get(self, scenario_id: str) -> Any: ...

    def all(self) -> list[Any]: ...


def build_entry(spec: ScenarioSpec) -> CatalogEntry:
    """Load what a session needs for `spec`: its rule engine and its sensors. Raises if either
    cannot be loaded."""
    engine = load_rule_engine(spec)
    picture = Picture.build(spec, spec.default_seed)  # the sensors must load
    return CatalogEntry(spec, engine, {s.id: s.params.modality for s in picture.suite.sensors})


class ScenarioCatalog:
    """Parses the scenario files once and keeps the playable ones. Scenarios saved in the database
    (authored or generated) are looked up after the packs, and built once per version of their
    content."""

    def __init__(self, root: Path | None = None, saved: SavedScenarios | None = None) -> None:
        self._root = root
        self._entries: dict[str, CatalogEntry] | None = None
        self._lock = threading.Lock()
        self._saved = saved
        self._built: dict[tuple[str, str], CatalogEntry | None] = {}

    def _load(self) -> dict[str, CatalogEntry]:
        root = self._root or packs_root() / "scenarios"
        found: dict[str, CatalogEntry] = {}
        for path in sorted([*root.glob("*.json"), *root.glob("*.yaml")]):
            try:
                spec = load_pack(path)
                if not isinstance(spec, ScenarioSpec):
                    continue
                found[spec.id] = build_entry(spec)
            except Exception as error:  # noqa: BLE001 - an unplayable scenario is only not listed
                log.warning("scenario %s is not playable: %r", path.name, error)
        return found

    def entries(self) -> dict[str, CatalogEntry]:
        with self._lock:
            if self._entries is None:
                self._entries = self._load()
            return self._entries

    def _saved_entry(self, spec: ScenarioSpec, sha: str) -> CatalogEntry | None:
        key = (spec.id, sha)
        with self._lock:
            if key not in self._built:
                try:
                    self._built[key] = build_entry(spec)
                except Exception as error:  # noqa: BLE001 - an unplayable scenario is not listed
                    log.warning("saved scenario %s is not playable: %r", spec.id, error)
                    self._built[key] = None
            return self._built[key]

    def saved_entries(self) -> dict[str, CatalogEntry]:
        """The playable saved scenarios that no pack scenario shadows."""
        if self._saved is None:
            return {}
        packs = self.entries()
        out: dict[str, CatalogEntry] = {}
        for item in self._saved.all():
            if item.spec.id in packs:
                continue
            entry = self._saved_entry(item.spec, item.spec_sha256)
            if entry is not None:
                out[item.spec.id] = entry
        return out

    def all_entries(self) -> dict[str, CatalogEntry]:
        """Pack scenarios, then saved ones."""
        return {**self.entries(), **self.saved_entries()}

    def get(self, scenario_id: str, version: str | None = None) -> CatalogEntry | None:
        entry = self.entries().get(scenario_id)
        if entry is None and self._saved is not None:
            item = self._saved.get(scenario_id)
            if item is not None:
                entry = self._saved_entry(item.spec, item.spec_sha256)
        if entry is not None and version is not None and entry.spec.version != version:
            return None
        return entry
